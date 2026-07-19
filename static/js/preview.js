const garmentStudio = document.querySelector('.garment-studio');

if (garmentStudio) {
  const imageIndex = Number(garmentStudio.dataset.imageIndex);
  const form = document.querySelector('#previewForm');
  const customerInput = document.querySelector('#customerInput');
  const charCount = document.querySelector('#previewCharCount');
  const submitButton = document.querySelector('#previewSubmit');
  const availability = document.querySelector('#previewAvailability');
  const serviceState = document.querySelector('#previewServiceState');
  const serviceText = document.querySelector('#previewServiceText');
  const progress = document.querySelector('#previewProgress');
  const progressTitle = document.querySelector('#previewProgressTitle');
  const progressMessage = document.querySelector('#previewProgressMessage');
  const progressBar = document.querySelector('#previewProgressBar');
  const progressValue = document.querySelector('#previewProgressValue');
  const errorView = document.querySelector('#previewError');
  const errorMessage = document.querySelector('#previewErrorMessage');
  const retryButton = document.querySelector('#previewRetry');
  const results = document.querySelector('#previewResults');
  const resultsSummary = document.querySelector('#previewResultsSummary');
  const imageGrid = document.querySelector('#previewImageGrid');
  let previewOnline = serviceState.dataset.status === 'online';
  let statusRequest = null;

  async function readPreviewJson(response) {
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.toLowerCase().includes('application/json')) {
      throw new Error(`服务返回了异常页面（HTTP ${response.status}），请稍后重试。`);
    }
    return response.json();
  }

  function setAvailability(online, message = '') {
    previewOnline = online;
    serviceState.dataset.status = online ? 'online' : 'offline';
    serviceText.textContent = online ? '成衣服务在线' : '成衣服务离线';
    serviceState.title = message;
    submitButton.disabled = !online;
    availability.hidden = online;
    availability.textContent = message || '成衣效果服务当前不在线，暂时无法提交。';
  }

  async function refreshPreviewStatus() {
    if (statusRequest) return statusRequest;
    statusRequest = (async () => {
      try {
        const response = await fetch('/api/preview-status', { cache: 'no-store' });
        const payload = await readPreviewJson(response);
        if (!response.ok) throw new Error(payload.message || '状态读取失败');
        setAvailability(payload.online, payload.workerId ? `节点：${payload.workerId}` : payload.message);
        return payload.online;
      } catch (_error) {
        setAvailability(false, '无法连接成衣效果服务，暂时无法提交。');
        return false;
      } finally {
        statusRequest = null;
      }
    })();
    return statusRequest;
  }

  function setProgress(value) {
    const normalized = Math.max(0, Math.min(100, Math.round(value)));
    progressBar.style.width = `${normalized}%`;
    progressValue.textContent = `${normalized}%`;
    if (normalized < 35) progressTitle.textContent = '正在理解设计需求';
    else if (normalized < 75) progressTitle.textContent = '正在生成成衣方案';
    else progressTitle.textContent = '正在整理效果图';
  }

  async function waitForPreviewResult(requestId) {
    const deadline = Date.now() + 305000;
    let value = 6;
    while (Date.now() < deadline) {
      const response = await fetch(`/api/preview-results/${requestId}`, { cache: 'no-store' });
      const payload = await readPreviewJson(response);
      if (response.status === 202) {
        value = Math.min(95, value + Math.max(1, Math.ceil((97 - value) * 0.045)));
        setProgress(value);
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        continue;
      }
      if (!response.ok) throw new Error(payload.message || '成衣效果生成失败。');
      if (payload.status === 'completed') return payload;
      throw new Error(payload.message || '成衣效果结果状态异常。');
    }
    throw new Error('成衣效果生成超时，请稍后重新提交。');
  }

  function renderImages(imageUrls, customerBrief) {
    imageGrid.replaceChildren();
    imageUrls.forEach((url, index) => {
      const link = document.createElement('a');
      link.className = 'garment-result-card';
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      const image = document.createElement('img');
      image.src = url;
      image.alt = `成衣效果方案 ${index + 1}`;
      image.loading = index > 1 ? 'lazy' : 'eager';
      image.referrerPolicy = 'no-referrer';

      const caption = document.createElement('span');
      caption.innerHTML = `<b>LOOK ${String(index + 1).padStart(2, '0')}</b><small>点击查看原图 ↗</small>`;
      link.append(image, caption);
      imageGrid.append(link);
    });
    resultsSummary.textContent = `基于“${customerBrief}”生成 ${imageUrls.length} 个方案`;
    results.hidden = false;
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  customerInput.addEventListener('input', () => {
    charCount.textContent = String(customerInput.value.length);
  });

  document.querySelectorAll('[data-preview-prompt]').forEach((button) => {
    button.addEventListener('click', () => {
      customerInput.value = button.dataset.previewPrompt;
      customerInput.dispatchEvent(new Event('input'));
      customerInput.focus();
    });
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const customerBrief = customerInput.value.trim();
    if (!customerBrief) return;
    if (!(await refreshPreviewStatus()) || !previewOnline) return;

    submitButton.disabled = true;
    submitButton.querySelector('span').textContent = '正在提交任务';
    progress.hidden = false;
    errorView.hidden = true;
    results.hidden = true;
    setProgress(0);
    progressMessage.textContent = 'Worker 正在结合蕾丝纹样与设计需求生成效果图，请保持页面开启。';

    try {
      const response = await fetch('/api/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Preview-Client-Version': 'garment-preview-v1',
        },
        body: JSON.stringify({ imageIndex, customerInput: customerBrief }),
      });
      const submission = await readPreviewJson(response);
      if (!response.ok) throw new Error(submission.message || '成衣任务提交失败。');
      if (!submission.requestId) throw new Error('成衣任务未返回任务编号。');

      const payload = await waitForPreviewResult(submission.requestId);
      setProgress(100);
      progressMessage.textContent = '成衣效果图已生成。';
      await new Promise((resolve) => window.setTimeout(resolve, 350));
      progress.hidden = true;
      renderImages(payload.imageUrls, customerBrief);
    } catch (error) {
      progress.hidden = true;
      errorMessage.textContent = error.message;
      errorView.hidden = false;
    } finally {
      submitButton.disabled = !previewOnline;
      submitButton.querySelector('span').textContent = '生成成衣效果';
    }
  });

  retryButton.addEventListener('click', () => {
    errorView.hidden = true;
    customerInput.focus();
  });

  refreshPreviewStatus();
  window.setInterval(refreshPreviewStatus, 5000);
}
