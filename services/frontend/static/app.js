"use strict";

// Profil client complet courant (toutes les colonnes features), servant de base a
// l'envoi vers /predict. Les champs editables du formulaire viennent l'ecraser.
let currentProfile = {};

const el = (id) => document.getElementById(id);

const EDITABLE = {
  "Contract": "f-contract",
  "Tenure Months": "f-tenure",
  "Monthly Charges": "f-monthly",
  "Internet Service": "f-internet",
};

function prettyOffer(value) {
  if (!value) return "—";
  return String(value).replace(/_/g, " ");
}

async function loadSample() {
  el("profile-ctx").textContent = "Chargement d'un client…";
  try {
    const res = await fetch("/api/sample");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    currentProfile = data.profile || {};
    // Pre-remplir les champs editables depuis le profil tire.
    for (const [col, inputId] of Object.entries(EDITABLE)) {
      if (currentProfile[col] !== undefined && currentProfile[col] !== "") {
        el(inputId).value = currentProfile[col];
      }
    }
    const city = currentProfile["City"] || "—";
    const gender = currentProfile["Gender"] || "—";
    const tenure = currentProfile["Tenure Months"] || "?";
    el("profile-ctx").textContent = `Client tiré au hasard · ${gender} · ${city} · ${tenure} mois d'ancienneté`;
    el("result").classList.add("hidden");
    el("predict-error").classList.add("hidden");
  } catch (err) {
    el("profile-ctx").textContent = "Impossible de charger un client (" + err.message + ")";
  }
}

function buildPayload() {
  const payload = { ...currentProfile };
  for (const [col, inputId] of Object.entries(EDITABLE)) {
    const val = el(inputId).value;
    if (val !== "") payload[col] = val;
  }
  // Garder currentProfile aligne avec les valeurs editees.
  currentProfile = payload;
  return payload;
}

async function predict() {
  const errBox = el("predict-error");
  errBox.classList.add("hidden");
  const btn = el("btn-predict");
  btn.disabled = true;
  btn.textContent = "Prédiction…";
  const t0 = performance.now();
  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    const elapsed = Math.round(performance.now() - t0);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));

    const prob = Number(data.churn_probability);
    const pct = Math.round(prob * 1000) / 10;
    el("churn-pct").textContent = pct + " %";
    el("churn-fill").style.width = Math.min(100, Math.max(0, pct)) + "%";
    const badge = el("risk-badge");
    if (prob >= 0.5) {
      badge.textContent = "Client à risque";
      badge.className = "risk-badge risk";
    } else {
      badge.textContent = "Client fidèle";
      badge.className = "risk-badge safe";
    }
    el("offer-value").textContent = prettyOffer(data.recommended_offer);
    el("latency").textContent = "Réponse en ≈ " + elapsed + " ms";
    el("result").classList.remove("hidden");
  } catch (err) {
    errBox.textContent = "Erreur de prédiction : " + err.message;
    errBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "Prédire le churn";
  }
}

function renderOffers(offers) {
  const container = el("offers-dist");
  const entries = Object.entries(offers || {});
  if (entries.length === 0) {
    container.innerHTML = '<p class="hint">Aucune donnée pour l\'instant.</p>';
    return;
  }
  const max = Math.max(...entries.map(([, c]) => c));
  entries.sort((a, b) => b[1] - a[1]);
  container.innerHTML = entries
    .map(([name, count]) => {
      const w = max ? Math.round((count / max) * 100) : 0;
      return `<div class="offer-row"><span>${prettyOffer(name)}</span>` +
        `<span class="bar"><span style="width:${w}%"></span></span>` +
        `<span class="count">${count}</span></div>`;
    })
    .join("");
}

async function refreshMetrics() {
  try {
    const res = await fetch("/api/metrics");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const m = await res.json();
    el("m-total").textContent = m.total_requests ?? "—";
    el("m-success").textContent = (m.success_rate_pct ?? "—") + " %";
    el("m-avg").textContent = (m.latency_avg_ms ?? "—") + " ms";
    el("m-p95").textContent = (m.latency_p95_ms ?? "—") + " ms";
    el("m-uptime").textContent = Math.round(m.uptime_s ?? 0) + " s";
    renderOffers(m.offers);
    el("metrics-updated").textContent = "màj " + new Date().toLocaleTimeString();
    setStatus(true);
  } catch (err) {
    setStatus(false);
  }
}

function setStatus(ok) {
  el("status-dot").className = "dot " + (ok ? "ok" : "ko");
  el("status-text").textContent = ok ? "Services connectés" : "Monitoring injoignable";
}

el("btn-sample").addEventListener("click", loadSample);
el("btn-predict").addEventListener("click", predict);

loadSample();
refreshMetrics();
setInterval(refreshMetrics, 4000);
