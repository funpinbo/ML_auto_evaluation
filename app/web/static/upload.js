// app/web/static/upload.js — 업로드 화면(FR-002) 바닐라 JS (frontend 소유, Node 빌드 없음).
// 모델/데이터 업로드 폼 제출 -> POST /models, /datasets 호출. 목록은 GET /models, /datasets
// 로 채운다. data-testid 네이밍 규칙은 app/web/templates/upload.html 상단 주석 참고.

(function () {
  "use strict";

  function qs(selector) {
    return document.querySelector(selector);
  }

  function setHidden(el, hidden) {
    if (el) el.hidden = hidden;
  }

  function showStatus(statusEl, errorEl, message) {
    setHidden(errorEl, true);
    if (errorEl) errorEl.textContent = "";
    if (statusEl) {
      statusEl.textContent = message;
      setHidden(statusEl, false);
    }
  }

  function showError(statusEl, errorEl, message) {
    setHidden(statusEl, true);
    if (statusEl) statusEl.textContent = "";
    if (errorEl) {
      errorEl.textContent = message;
      setHidden(errorEl, false);
    }
  }

  function formatDetail(detail) {
    // 02§6: 에러 응답은 FastAPI 기본 포맷 {"detail": "..."}. `detail` 은 보통 문자열(예:
    // predict 계약 위반 메시지, AC-4)이지만, pydantic 필수 필드 누락(AC-6, problem_type
    // 미선택)처럼 422 응답은 `detail` 이 [{loc, msg, ...}] 배열 형태다 — 그대로
    // textContent 에 넣으면 "[object Object]"로 보이므로 사람이 읽을 문장으로 풀어준다.
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (item) {
          if (item && typeof item === "object") {
            var loc = Array.isArray(item.loc) ? item.loc.join(".") : "";
            return (loc ? loc + ": " : "") + (item.msg || JSON.stringify(item));
          }
          return String(item);
        })
        .join("; ");
    }
    if (detail && typeof detail === "object") return JSON.stringify(detail);
    return String(detail);
  }

  async function parseErrorDetail(response) {
    try {
      var body = await response.json();
      if (body && body.detail !== undefined && body.detail !== null) {
        return formatDetail(body.detail);
      }
    } catch (err) {
      // 응답이 JSON 이 아닌 경우(네트워크 오류 등) 기본 메시지로 대체.
    }
    return "업로드에 실패했습니다 (상태 코드: " + response.status + ").";
  }

  function renderModelList(models) {
    var list = qs('[data-testid="model-list"]');
    if (!list) return;
    if (!models || models.length === 0) {
      list.innerHTML =
        '<li class="empty" data-testid="model-list-empty">아직 업로드된 모델이 없습니다.</li>';
      return;
    }
    list.innerHTML = "";
    models.forEach(function (m) {
      var li = document.createElement("li");
      li.setAttribute("data-testid", "model-list-item");
      li.setAttribute("data-model-id", m.model_id);
      li.textContent = m.name + " (" + m.framework + " / " + m.problem_type + ")";
      list.appendChild(li);
    });
  }

  function renderDatasetList(datasets) {
    var list = qs('[data-testid="dataset-list"]');
    if (!list) return;
    if (!datasets || datasets.length === 0) {
      list.innerHTML =
        '<li class="empty" data-testid="dataset-list-empty">아직 업로드된 데이터셋이 없습니다.</li>';
      return;
    }
    list.innerHTML = "";
    datasets.forEach(function (d) {
      var li = document.createElement("li");
      li.setAttribute("data-testid", "dataset-list-item");
      li.setAttribute("data-dataset-id", d.dataset_id);
      li.textContent = d.name;
      list.appendChild(li);
    });
  }

  async function fetchModels() {
    var list = qs('[data-testid="model-list"]');
    if (!list) return;
    list.innerHTML = '<li data-testid="model-list-loading">모델 목록을 불러오는 중...</li>';
    try {
      var res = await fetch("/models");
      if (!res.ok) throw new Error("GET /models failed: " + res.status);
      renderModelList(await res.json());
    } catch (err) {
      list.innerHTML =
        '<li class="error" data-testid="model-list-error">모델 목록을 불러오지 못했습니다.</li>';
    }
  }

  async function fetchDatasets() {
    var list = qs('[data-testid="dataset-list"]');
    if (!list) return;
    list.innerHTML = '<li data-testid="dataset-list-loading">데이터셋 목록을 불러오는 중...</li>';
    try {
      var res = await fetch("/datasets");
      if (!res.ok) throw new Error("GET /datasets failed: " + res.status);
      renderDatasetList(await res.json());
    } catch (err) {
      list.innerHTML =
        '<li class="error" data-testid="dataset-list-error">데이터셋 목록을 불러오지 못했습니다.</li>';
    }
  }

  function bindUploadForm(options) {
    var form = qs('[data-testid="' + options.formTestId + '"]');
    if (!form) return;
    var statusEl = qs('[data-testid="' + options.statusTestId + '"]');
    var errorEl = qs('[data-testid="' + options.errorTestId + '"]');
    var submitBtn = qs('[data-testid="' + options.submitTestId + '"]');

    form.addEventListener("submit", async function (evt) {
      evt.preventDefault();
      if (submitBtn) submitBtn.disabled = true;
      showStatus(statusEl, errorEl, "업로드 중...");

      var formData = new FormData(form);
      try {
        var res = await fetch(options.endpoint, { method: "POST", body: formData });
        if (!res.ok) {
          showError(statusEl, errorEl, await parseErrorDetail(res));
          return;
        }
        var body = await res.json();
        showStatus(statusEl, errorEl, options.successMessage(body));
        form.reset();
        await options.refresh();
      } catch (err) {
        showError(statusEl, errorEl, "네트워크 오류로 업로드에 실패했습니다.");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindUploadForm({
      formTestId: "model-upload-form",
      statusTestId: "model-upload-status",
      errorTestId: "model-upload-error",
      submitTestId: "model-upload-submit",
      endpoint: "/models",
      successMessage: function (body) {
        return "업로드 성공 (model_id: " + body.model_id + ")";
      },
      refresh: fetchModels,
    });

    bindUploadForm({
      formTestId: "dataset-upload-form",
      statusTestId: "dataset-upload-status",
      errorTestId: "dataset-upload-error",
      submitTestId: "dataset-upload-submit",
      endpoint: "/datasets",
      successMessage: function (body) {
        return "업로드 성공 (dataset_id: " + body.dataset_id + ")";
      },
      refresh: fetchDatasets,
    });

    fetchModels();
    fetchDatasets();
  });
})();
