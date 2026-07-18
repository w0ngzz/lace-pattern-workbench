const uploadForm = document.querySelector("#uploadForm");

if (uploadForm) {
  const fileInput = document.querySelector("#patternFile");
  const fileLabel = document.querySelector("#fileLabel");
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

  fileInput.addEventListener("change", () => {
    fileLabel.textContent = fileInput.files[0]?.name || "选择或拖入客户参考图";
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
    fileLabel.textContent = "选择或拖入客户参考图";
    uploadForm.hidden = false;
    progressView.hidden = true;
    resultView.hidden = true;
    customerForm.reset();
    matchStatus = "unknown";
    window.location.hash = "recognition";
  });
}
