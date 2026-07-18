const uploadForm = document.querySelector("#uploadForm");
const panelMatcherStatus = document.querySelector('#panelMatcherStatus');
const panelMatcherStatusText = document.querySelector('#panelMatcherStatusText');
let matcherOnline = false;
let statusRequest = null;

async function readJsonResponse(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error(`服务返回了异常页面（HTTP ${response.status}），请稍后重试。`);
  }
  return response.json();
}

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
      const payload = await readJsonResponse(response);
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
  const matchCandidates = document.querySelector("#matchCandidates");
  const candidateActions = document.querySelector("#candidateActions");
  const confirmCandidate = document.querySelector("#confirmCandidate");
  const rejectAllMatches = document.querySelector("#rejectAllMatches");
  const previewAction = document.querySelector("#previewAction");
  const previewLink = document.querySelector("#previewLink");
  const workOrderQuestion = document.querySelector("#workOrderQuestion");
  const workOrderQuestionText = document.querySelector("#workOrderQuestionText");
  const customerForm = document.querySelector("#customerForm");
  const resetFinder = document.querySelector("#resetFinder");
  let uploadFileName = "";
  let matchStatus = "unknown";
  let selectedCandidate = null;

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

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  async function waitForMatchResult(requestId) {
    const deadline = Date.now() + 125000;
    let progress = 8;

    while (Date.now() < deadline) {
      const response = await fetch(`/api/match-results/${requestId}`, {
        cache: 'no-store',
      });
      const payload = await readJsonResponse(response);

      if (response.status === 202) {
        progress = Math.min(94, progress + Math.max(1, Math.ceil((96 - progress) * 0.08)));
        setProgress(progress);
        await wait(1000);
        continue;
      }
      if (!response.ok) {
        throw new Error(payload.message || '图案识别服务处理失败。');
      }
      if (payload.status === 'completed') return payload;
      throw new Error(payload.message || '图案匹配结果状态异常。');
    }

    throw new Error('图案识别服务响应超时，请重新上传或创建设计工单。');
  }

  function showWorkOrderQuestion(message = '候选款式均不符合需求，是否创建设计工单？') {
    candidateActions.hidden = true;
    previewAction.hidden = true;
    workOrderQuestionText.textContent = message;
    workOrderQuestion.hidden = false;
  }

  function selectCandidate(button, candidate) {
    selectedCandidate = candidate;
    matchStatus = "unknown";
    workOrderQuestion.hidden = true;
    customerForm.hidden = true;
    previewAction.hidden = true;
    candidateActions.hidden = false;
    matchCandidates.querySelectorAll('.match-candidate').forEach((item) => {
      const selected = item === button;
      item.classList.toggle('is-selected', selected);
      item.setAttribute('aria-selected', String(selected));
    });
    confirmCandidate.disabled = false;
    const displayName = candidate.styleCode || candidate.fileName;
    confirmCandidate.textContent = `确认选择 ${displayName}`;
    resultMessage.textContent = `已选中 ${displayName}，相似度 ${(candidate.similarity * 100).toFixed(1)}%，确认后可继续预览。`;
  }

  function renderCandidates(rawCandidates) {
    matchCandidates.replaceChildren();
    selectedCandidate = null;
    confirmCandidate.disabled = true;
    confirmCandidate.textContent = '确认选择此款';

    const candidates = Array.isArray(rawCandidates) ? rawCandidates.slice(0, 5) : [];
    candidates.forEach((candidate, index) => {
      const similarity = Number(candidate.similarity);
      if (!candidate.fileName || !candidate.matchedImage || !Number.isFinite(similarity)) return;

      const button = document.createElement('button');
      button.className = 'match-candidate';
      button.type = 'button';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', 'false');

      const visual = document.createElement('span');
      visual.className = 'match-candidate-visual';
      const image = document.createElement('img');
      image.src = candidate.matchedImage;
      image.alt = `候选款式 ${candidate.styleCode || candidate.fileName}`;
      const rank = document.createElement('span');
      rank.className = 'match-candidate-rank';
      rank.textContent = String(index + 1).padStart(2, '0');
      visual.append(image, rank);

      const details = document.createElement('span');
      details.className = 'match-candidate-details';
      const name = document.createElement('strong');
      name.textContent = candidate.styleCode || candidate.fileName;
      const score = document.createElement('small');
      score.textContent = `${candidate.category || '蕾丝纹样'} · ${(similarity * 100).toFixed(1)}%`;
      details.append(name, score);
      button.append(visual, details);
      button.addEventListener('click', () => selectCandidate(button, { ...candidate, similarity }));
      matchCandidates.append(button);
    });

    const hasCandidates = matchCandidates.childElementCount > 0;
    matchCandidates.hidden = !hasCandidates;
    candidateActions.hidden = !hasCandidates;
    return matchCandidates.childElementCount;
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
      const response = await fetch("/api/match", {
        method: "POST",
        headers: { "X-Match-Client-Version": "top5-results-v2" },
        body: formData,
      });
      const submission = await readJsonResponse(response);
      if (!response.ok) throw new Error(submission.message || "识别请求失败，请稍后重试。");
      if (!submission.requestId) throw new Error("识别任务创建失败，未返回任务编号。");

      const payload = await waitForMatchResult(submission.requestId);

      setProgress(100);
      await new Promise((resolve) => window.setTimeout(resolve, 280));
      progressView.hidden = true;
      resultView.hidden = false;
      setMatchStep(3);
      workOrderQuestion.hidden = true;
      customerForm.hidden = true;
      previewAction.hidden = true;
      matchStatus = "unknown";

      const candidateCount = renderCandidates(payload.matches);
      if (candidateCount) {
        resultTitle.textContent = "请选择合适的款式";
        resultMessage.textContent = `Worker 返回了 ${candidateCount} 个相似候选，请选择最符合客户需求的一款。`;
      } else {
        matchStatus = "not_matched";
        resultTitle.textContent = payload.message || "暂未找到合适款式";
        resultMessage.textContent = "Worker 没有返回可用候选款式，可继续创建内部设计工单并登记客户信息。";
        showWorkOrderQuestion('素材库暂未提供合适款式，是否创建设计工单？');
      }
    } catch (error) {
      matchStatus = "not_matched";
      progressView.hidden = true;
      resultView.hidden = false;
      setMatchStep(3);
      matchCandidates.replaceChildren();
      matchCandidates.hidden = true;
      candidateActions.hidden = true;
      previewAction.hidden = true;
      customerForm.hidden = true;
      resultTitle.textContent = "识别未完成";
      resultMessage.textContent = error.message;
      showWorkOrderQuestion('识别任务未能完成，是否创建设计工单继续跟进？');
    }
  });

  confirmCandidate.addEventListener("click", () => {
    if (!selectedCandidate) return;
    matchStatus = "matched";
    matchCandidates.querySelectorAll('.match-candidate').forEach((button) => {
      button.disabled = true;
    });
    candidateActions.hidden = true;
    previewAction.hidden = false;
    previewLink.href = selectedCandidate.previewUrl;
    resultTitle.textContent = "款式已确认";
    resultMessage.textContent = `已确认 ${selectedCandidate.styleCode || selectedCandidate.fileName} 符合需求，可以继续查看成衣效果。`;
  });

  rejectAllMatches.addEventListener("click", () => {
    matchStatus = "rejected";
    selectedCandidate = null;
    matchCandidates.querySelectorAll('.match-candidate').forEach((button) => {
      button.classList.remove('is-selected');
      button.setAttribute('aria-selected', 'false');
    });
    resultTitle.textContent = "候选款式均不合适";
    resultMessage.textContent = "已确认本次 Top 5 候选均不符合客户需求，可创建内部设计工单继续跟进。";
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
      const payload = await readJsonResponse(response);
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
    selectedCandidate = null;
    matchCandidates.replaceChildren();
    matchCandidates.hidden = true;
    candidateActions.hidden = true;
    workOrderQuestion.hidden = true;
    previewAction.hidden = true;
    setMatchStep(1);
    window.location.hash = "recognition";
  });
}
