const uploadForm = document.querySelector("#uploadForm");
const panelMatcherStatus = document.querySelector('#panelMatcherStatus');
const panelMatcherStatusText = document.querySelector('#panelMatcherStatusText');
let matcherOnline = false;
let statusRequest = null;

function applyMatcherAvailability(online, message = '') {
  matcherOnline = online;
  const fileInput = document.querySelector('#patternFile');
  const matchButton = document.querySelector('#matchButton');
  const availability = document.querySelector('#matcherAvailability');

  if (fileInput) fileInput.disabled = !online;
  if (matchButton) matchButton.disabled = !online;
  if (panelMatcherStatus && panelMatcherStatusText) {
    panelMatcherStatus.dataset.status = online ? 'online' : 'offline';
    panelMatcherStatusText.textContent = online ? '服务在线' : '服务离线';
    panelMatcherStatus.title = message;
  }
  if (availability) {
    availability.hidden = online;
    availability.textContent = message || '图案识别服务当前不在线，暂时无法上传和匹配。';
  }
}

async function refreshMatcherStatus() {
  if (statusRequest) return statusRequest;
  statusRequest = (async () => {
    try {
      const response = await fetch('/api/matcher-status', { cache: 'no-store' });
      if (!response.ok) throw new Error('status request failed');
      const payload = await response.json();
      const statusMessage = payload.workerId ? `节点：${payload.workerId}` : payload.message;
      applyMatcherAvailability(payload.online, statusMessage);
      return payload.online;
    } catch (_error) {
      applyMatcherAvailability(false, '无法连接图案识别服务，暂时无法上传和匹配。');
      return false;
    } finally {
      statusRequest = null;
    }
  })();
  return statusRequest;
}

if (panelMatcherStatus && panelMatcherStatusText) {
  refreshMatcherStatus();
  window.setInterval(refreshMatcherStatus, 5000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshMatcherStatus();
  });
}

const patternModal = document.querySelector('#patternModal');

if (patternModal) {
  const modalImage = document.querySelector('#modalPatternImage');
  const modalTitle = document.querySelector('#modalPatternTitle');
  const modalDescription = document.querySelector('#modalPatternDescription');
  const modalReason = document.querySelector('#modalPatternReason');
  const modalApplication = document.querySelector('#modalPatternApplication');
  const modalCloseButton = patternModal.querySelector('.pattern-modal-close');
  let activePatternTrigger = null;

  function openPatternModal(trigger) {
    activePatternTrigger = trigger;
    modalImage.src = trigger.dataset.image;
    modalImage.alt = `${trigger.dataset.title}蕾丝图案详情`;
    modalTitle.textContent = trigger.dataset.title;
    modalDescription.textContent = trigger.dataset.description;
    modalReason.textContent = trigger.dataset.reason;
    modalApplication.textContent = trigger.dataset.application;
    patternModal.hidden = false;
    document.body.classList.add('modal-open');
    modalCloseButton.focus();
  }

  function closePatternModal() {
    patternModal.hidden = true;
    document.body.classList.remove('modal-open');
    activePatternTrigger?.focus();
  }

  document.querySelectorAll('.pattern-detail-trigger').forEach((trigger) => {
    trigger.addEventListener('click', () => openPatternModal(trigger));
  });

  patternModal.querySelectorAll('[data-close-pattern-modal]').forEach((button) => {
    button.addEventListener('click', closePatternModal);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !patternModal.hidden) closePatternModal();
  });
}

if (uploadForm) {
  const fileInput = document.querySelector("#patternFile");
  const fileLabel = document.querySelector("#fileLabel");
  const dropZone = document.querySelector("#dropZone");
  const matchSteps = document.querySelectorAll("#matchSteps .match-step");
  const progressView = document.querySelector("#progressView");
  const progressBar = document.querySelector("#progressBar");
  const progressValue = document.querySelector("#progressValue");
  const progressLabel = document.querySelector("#progressLabel");
  const resultView = document.querySelector("#resultView");
  const resultTitle = document.querySelector("#resultTitle");
  const resultMessage = document.querySelector("#resultMessage");
  const resultImage = document.querySelector("#resultImage");
  const resultImageWrap = document.querySelector("#resultImageWrap");
  const confirmActions = document.querySelector("#confirmActions");
  const previewAction = document.querySelector("#previewAction");
  const previewLink = document.querySelector("#previewLink");
  const workOrderQuestion = document.querySelector("#workOrderQuestion");
  const customerForm = document.querySelector("#customerForm");
  const resetFinder = document.querySelector("#resetFinder");
  let uploadFileName = "";
  let matchStatus = "unknown";

  function setMatchStep(activeStep) {
    matchSteps.forEach((step) => {
      const stepNumber = Number(step.dataset.step);
      step.classList.toggle('is-active', stepNumber === activeStep);
      step.classList.toggle('is-complete', stepNumber < activeStep);
      if (stepNumber === activeStep) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
  }

  fileInput.addEventListener("change", () => {
    fileLabel.textContent = fileInput.files[0]?.name || "拖拽或选择客户参考图";
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (!fileInput.disabled) dropZone.classList.add('is-dragover');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove('is-dragover');
    });
  });

  dropZone.addEventListener('drop', (event) => {
    if (fileInput.disabled) return;
    const file = event.dataTransfer?.files[0];
    if (!file || !file.type.startsWith('image/')) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    fileLabel.textContent = file.name;
  });

  function setProgress(value) {
    progressBar.style.width = `${value}%`;
    progressValue.textContent = `${value}%`;
    if (value < 35) progressLabel.textContent = "正在读取图案纹理…";
    else if (value < 72) progressLabel.textContent = "正在检索蕾丝素材库…";
    else progressLabel.textContent = "正在整理匹配结果…";
  }

  // 临时进度方案：用分段延时模拟识图过程，后续替换为真实任务进度或轮询接口。
  function simulateProgress() {
    return new Promise((resolve) => {
      let value = 0;
      const timer = window.setInterval(() => {
        value = Math.min(94, value + Math.ceil(Math.random() * 8));
        setProgress(value);
        if (value >= 94) {
          window.clearInterval(timer);
          window.setTimeout(resolve, 420);
        }
      }, 150);
    });
  }

  function showWorkOrderQuestion() {
    confirmActions.hidden = true;
    previewAction.hidden = true;
    workOrderQuestion.hidden = false;
  }

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!fileInput.files.length) return;

    // 上传前强制刷新一次状态，避免使用定时轮询留下的旧在线结果。
    const serviceOnline = await refreshMatcherStatus();
    if (!serviceOnline || !matcherOnline) return;

    setMatchStep(2);
    uploadFileName = fileInput.files[0].name;
    uploadForm.hidden = true;
    resultView.hidden = true;
    progressView.hidden = false;
    setProgress(0);

    try {
      const formData = new FormData();
      formData.append("pattern", fileInput.files[0]);
      const [response] = await Promise.all([
        fetch("/api/match", { method: "POST", body: formData }),
        simulateProgress(),
      ]);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || "识别请求失败，请稍后重试。");

      setProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 280));
      progressView.hidden = true;
      resultView.hidden = false;
      setMatchStep(3);
      workOrderQuestion.hidden = true;
      customerForm.hidden = true;
      previewAction.hidden = true;

      resultTitle.textContent = payload.message;
      if (payload.matched) {
        matchStatus = "matched";
        resultMessage.textContent = `素材库中找到了同名图案 ${payload.fileName}，请确认是否符合您的需求。`;
        resultImage.src = payload.matchedImage;
        resultImageWrap.hidden = false;
        confirmActions.hidden = false;
        previewLink.href = payload.previewUrl;
      } else {
        matchStatus = "not_matched";
        resultMessage.textContent = "当前素材库没有同名图案，可继续创建内部设计工单并登记客户信息。";
        resultImageWrap.hidden = true;
        confirmActions.hidden = true;
        showWorkOrderQuestion();
      }
    } catch (error) {
      progressView.hidden = true;
      resultView.hidden = false;
      setMatchStep(3);
      resultImageWrap.hidden = true;
      confirmActions.hidden = true;
      resultTitle.textContent = "识别未完成";
      resultMessage.textContent = error.message;
    }
  });

  document.querySelector("#confirmMatch").addEventListener("click", () => {
    confirmActions.hidden = true;
    previewAction.hidden = false;
    resultMessage.textContent = "已确认图案符合需求，可以继续查看成衣效果。";
  });

  document.querySelector("#rejectMatch").addEventListener("click", () => {
    matchStatus = "rejected";
    resultMessage.textContent = "已标记为不是这一款，可创建内部设计工单继续跟进。";
    showWorkOrderQuestion();
  });

  document.querySelector("#createWorkOrder").addEventListener("click", () => {
    workOrderQuestion.hidden = true;
    customerForm.hidden = false;
    resultTitle.textContent = "登记客户信息";
    resultMessage.textContent = "完成登记后，系统会为这次未匹配需求生成设计工单。";
  });

  document.querySelector("#skipWorkOrder").addEventListener("click", () => {
    workOrderQuestion.hidden = true;
    resultMessage.textContent = "本次识别已结束，您可以随时重新上传其他图案。";
  });

  customerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = customerForm.querySelector("button[type='submit']");
    const fields = new FormData(customerForm);
    submitButton.disabled = true;
    submitButton.textContent = "正在创建工单…";
    try {
      const response = await fetch("/api/work-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customerName: fields.get("customerName"),
          customerContact: fields.get("customerContact"),
          uploadFileName,
          matchStatus,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || "提交失败，请稍后重试。");
      customerForm.hidden = true;
      resultTitle.textContent = "工单创建成功";
      resultMessage.textContent = payload.message;
    } catch (error) {
      resultMessage.textContent = error.message;
      submitButton.disabled = false;
      submitButton.textContent = "登记并创建工单";
    }
  });

  resetFinder.addEventListener("click", () => {
    uploadForm.reset();
    fileLabel.textContent = "拖拽或选择客户参考图";
    uploadForm.hidden = false;
    progressView.hidden = true;
    resultView.hidden = true;
    customerForm.reset();
    matchStatus = "unknown";
    setMatchStep(1);
    window.location.hash = "recognition";
  });
}
