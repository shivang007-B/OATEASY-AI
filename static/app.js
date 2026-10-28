/**
 * FreshFlow — Minimal Intelligence Dashboard
 * Accordion rows · Scrollytelling · Clean tab transitions
 */

// ─── Scrollytelling observer ───────────────────────────────────────────────
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('in-view');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

function observeRevealEls() {
  document.querySelectorAll('.scroll-reveal').forEach(el => {
    if (!el.classList.contains('in-view')) revealObserver.observe(el);
  });
}

// ─── Accordion helper ──────────────────────────────────────────────────────
function toggleAcc(item) {
  item.classList.toggle('open');
}

function buildChevron() {
  return `<svg class="acc-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="4 6 8 10 12 6"/>
  </svg>`;
}

// ─── Badge helper ──────────────────────────────────────────────────────────
function riskBadge(level) {
  if (level === 'High')   return `<span class="badge badge-danger">${level}</span>`;
  if (level === 'Medium') return `<span class="badge badge-warn">${level}</span>`;
  return `<span class="badge badge-success">${level}</span>`;
}

// ─── Demand histogram (home page) ─────────────────────────────────────────
const HOUR_DATA = [
  { h:'11:00', buf:15, pred:10 }, { h:'12:00', buf:33, pred:25 },
  { h:'13:00', buf:63, pred:59 }, { h:'14:00', buf:51, pred:47 },
  { h:'15:00', buf:7,  pred:5  }, { h:'16:00', buf:11, pred:9  },
  { h:'17:00', buf:17, pred:15 }, { h:'18:00', buf:45, pred:41 },
  { h:'19:00', buf:38, pred:34 }, { h:'20:00', buf:67, pred:64 },
  { h:'21:00', buf:57, pred:53 }, { h:'22:00', buf:27, pred:23 },
];

function renderHistogram() {
  const barsEl = document.getElementById('demandHistogram');
  const labelsEl = document.getElementById('demandHistogramLabels');
  if (!barsEl) return;
  const maxH = Math.max(...HOUR_DATA.map(d => d.buf));
  barsEl.innerHTML = HOUR_DATA.map(d => {
    const bufPct  = Math.round(d.buf  / maxH * 100);
    const predPct = Math.round(d.pred / maxH * 100);
    return `<div class="chart-bar-col" title="${d.h}: ${d.pred} predicted">
      <div class="chart-bar" style="height:${bufPct}%;">
        <div class="chart-bar-fill" style="height:${predPct}%;"></div>
      </div>
    </div>`;
  }).join('');
  labelsEl.innerHTML = HOUR_DATA.map((d,i) =>
    `<span ${i===2||i===9 ? 'style="font-weight:600;color:var(--text-2);"' : ''}>${d.h}</span>`
  ).join('');
}

// ─── Main app class ────────────────────────────────────────────────────────
class FreshFlowApp {
  constructor() {
    this.currentTab = 'home';
    this.selectedRestaurant = 'R01';
    this.ingredientsList = [];
    this.init();
  }

  async init() {
    this.bindEvents();
    renderHistogram();
    await this.loadInitialData();
    this.switchTab('home');
    observeRevealEls();
  }

  bindEvents() {
    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        const tab = e.currentTarget.getAttribute('data-tab');
        if (tab) this.switchTab(tab);
      });
    });

    const restSelect = document.getElementById('restaurantSelect');
    if (restSelect) restSelect.addEventListener('change', e => {
      this.selectedRestaurant = e.target.value;
      this.refreshCurrentView();
    });

    const btnRun = document.getElementById('btnRunAnalysis');
    if (btnRun) btnRun.addEventListener('click', () => this.runDailyAnalysis());

    const btnQ = document.getElementById('btnQuickRefresh');
    if (btnQ) btnQ.addEventListener('click', () => {
      btnQ.disabled = true;
      this.loadReportSummary().finally(() => { btnQ.disabled = false; });
    });

    const invSearch = document.getElementById('inventorySearch');
    const invCat    = document.getElementById('inventoryCategoryFilter');
    const invRisk   = document.getElementById('inventoryRiskFilter');
    if (invSearch) invSearch.addEventListener('input', () => this.loadInventory());
    if (invCat)    invCat.addEventListener('change', () => this.loadInventory());
    if (invRisk)   invRisk.addEventListener('change', () => this.loadInventory());

    const fcCat = document.getElementById('forecastCategoryFilter');
    if (fcCat) fcCat.addEventListener('change', () => this.loadForecasts());

    const actType   = document.getElementById('actionTypeFilter');
    const actStatus = document.getElementById('actionStatusFilter');
    if (actType)   actType.addEventListener('change', () => this.loadActions());
    if (actStatus) actStatus.addEventListener('change', () => this.loadActions());
  }

  switchTab(rawTab) {
    const tab = rawTab === 'inventory' ? 'stock' : rawTab.toLowerCase();
    this.currentTab = tab;

    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tab);
    });

    document.querySelectorAll('.mobile-nav-item[data-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tab);
    });

    if (window.closeMobileSidebar) {
      window.closeMobileSidebar();
    }

    document.querySelectorAll('.tab-content').forEach(sec => {
      const isTarget = sec.id === `tab-${tab}`;
      if (isTarget) {
        sec.classList.remove('active');
        void sec.offsetWidth;
        sec.classList.add('active');
        sec.style.display = 'block';
      } else {
        sec.classList.remove('active');
        sec.style.display = 'none';
      }
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
    this.refreshCurrentView();
    setTimeout(observeRevealEls, 50);
  }

  refreshCurrentView() {
    switch (this.currentTab) {
      case 'home':     this.loadReportSummary(); this.loadHomePreviews(); break;
      case 'stock':    this.loadInventory(); break;
      case 'forecast': this.loadForecasts(); this.loadPurchasePlan(); break;
      case 'actions':  this.loadActions(); break;
      case 'analytics':this.loadAnalytics(); break;
      case 'account':  if (window.loadOwnerAccountDetails) window.loadOwnerAccountDetails(); break;
    }
  }

  async loadInitialData() {
    try {
      const res  = await fetch('/api/v1/inventory?restaurant_id=R01');
      const data = await res.json();
      if (data?.items) {
        this.ingredientsList = data.items;
        this.populateIngredientModals();
      }
    } catch(e) { console.warn('Pre-fetch ingredients:', e); }
  }

  populateIngredientModals() {
    ['modalAddStockIng','modalWasteIng'].forEach(id => {
      const sel = document.getElementById(id);
      if (!sel) return;
      sel.innerHTML = this.ingredientsList.map(i =>
        `<option value="${i.ingredient_id}">${i.ingredient_name} (${i.unit})</option>`
      ).join('');
    });
  }

  // ── HOME ──────────────────────────────────────────────────────────────
  async loadReportSummary() {
    try {
      const res  = await fetch(`/api/v1/reports/latest?restaurant_id=${this.selectedRestaurant}`);
      const data = await res.json();

      document.getElementById('reportPlanningDate').textContent = data.planning_date || '—';
      document.getElementById('reportAsOfDate').textContent     = (data.as_of || '—') + ' (22:45 IST)';

      document.getElementById('kpiPredictedOrders').textContent    = (data.predicted_orders_total || 0).toLocaleString();
      document.getElementById('kpiIngredientsAtRisk').textContent  = data.ingredients_at_risk || 0;
      document.getElementById('kpiPurchaseValue').textContent      = `₹${(data.recommended_purchase_value_inr || 0).toLocaleString(undefined, {minimumFractionDigits:2})}`;
      document.getElementById('kpiWasteAvoided').textContent       = `₹${(data.potential_waste_avoided_inr_estimated || 0).toLocaleString(undefined, {minimumFractionDigits:2})}`;

      if (data.top_priority) {
        document.getElementById('priorityActionTitle').textContent = data.top_priority.title;
        document.getElementById('priorityActionWhy').textContent   = data.top_priority.why;
        document.getElementById('priorityActionCost').textContent  = `₹${(data.top_priority.avoidable_cost_inr || 0).toLocaleString(undefined, {minimumFractionDigits:2})}`;
      }

      if (data.note) {
        document.getElementById('reportNoteText').innerHTML = `<strong>Estimated, not verified.</strong> ${data.note}`;
      }
    } catch(e) { console.error('Report summary:', e); }
  }

  async loadHomePreviews() {
    try {
      // Risk preview
      const rData = await fetch(`/api/v1/inventory/risks?restaurant_id=${this.selectedRestaurant}`).then(r=>r.json());
      const riskList = document.getElementById('homeRiskList');
      const topRisks = (rData.risks || []).slice(0, 5);
      if (!topRisks.length) {
        riskList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No critical risks detected.</div>';
      } else {
        riskList.innerHTML = topRisks.map(item => `
          <div class="acc-item">
            <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
              <div class="acc-trigger-left">
                ${riskBadge(item.risk_level)}
                <span class="acc-name">${item.ingredient_name}</span>
                <span class="acc-meta">${item.min_days_to_expiry}d expiry</span>
              </div>
              <div class="acc-trigger-right">
                <span style="font-size:0.82rem;font-weight:700;color:var(--danger);">₹${item.financial_exposure_inr.toFixed(0)}</span>
                ${buildChevron()}
              </div>
            </button>
            <div class="acc-body">
              <div class="acc-detail-grid">
                <div class="acc-detail-item"><div class="acc-detail-label">Stock</div><div class="acc-detail-value">${item.closing_stock_qty} ${item.unit}</div></div>
                <div class="acc-detail-item"><div class="acc-detail-label">Min Expiry</div><div class="acc-detail-value ${item.min_days_to_expiry<=2?'danger':''}">${item.min_days_to_expiry} days</div></div>
                <div class="acc-detail-item"><div class="acc-detail-label">Risk Prob</div><div class="acc-detail-value">${Math.round(item.risk_prob_next_3d*100)}%</div></div>
                <div class="acc-detail-item"><div class="acc-detail-label">Exposure</div><div class="acc-detail-value danger">₹${item.financial_exposure_inr.toFixed(2)}</div></div>
              </div>
            </div>
          </div>`).join('');
      }

      // Forecast preview
      const fData = await fetch(`/api/v1/forecasts?restaurant_id=${this.selectedRestaurant}`).then(r=>r.json());
      const fcList = document.getElementById('homeForecastList');
      const topDishes = (fData.forecasts || []).slice(0, 5);
      if (!topDishes.length) {
        fcList.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No forecasts available.</div>';
      } else {
        fcList.innerHTML = topDishes.map(d => `
          <div class="acc-item">
            <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
              <div class="acc-trigger-left">
                <span class="acc-name">${d.dish_name}</span>
                <span class="acc-meta">${d.category}</span>
              </div>
              <div class="acc-trigger-right">
                <span style="font-size:0.88rem;font-weight:700;color:var(--text-1);">${d.predicted_orders_median}</span>
                <span class="badge badge-dark">${d.suggested_prep_qty} prep</span>
                ${buildChevron()}
              </div>
            </button>
            <div class="acc-body">
              <div class="acc-detail-grid">
                <div class="acc-detail-item"><div class="acc-detail-label">Median Orders</div><div class="acc-detail-value">${d.predicted_orders_median}</div></div>
                <div class="acc-detail-item"><div class="acc-detail-label">80% Range</div><div class="acc-detail-value">${d.lower_80} – ${d.upper_80}</div></div>
                <div class="acc-detail-item"><div class="acc-detail-label">Suggested Prep</div><div class="acc-detail-value">${d.suggested_prep_qty} portions</div></div>
              </div>
            </div>
          </div>`).join('');
      }
    } catch(e) { console.error('Home previews:', e); }
  }

  // ── STOCK ─────────────────────────────────────────────────────────────
  async loadInventory() {
    try {
      const search = document.getElementById('inventorySearch')?.value || '';
      const cat    = document.getElementById('inventoryCategoryFilter')?.value || 'all';
      const risk   = document.getElementById('inventoryRiskFilter')?.value || 'all';

      let url = `/api/v1/inventory?restaurant_id=${this.selectedRestaurant}`;
      if (cat !== 'all')  url += `&category=${cat}`;
      if (risk !== 'all') url += `&risk_level=${risk}`;
      if (search)         url += `&search=${encodeURIComponent(search)}`;

      const data = await fetch(url).then(r=>r.json());
      const list = document.getElementById('inventoryAccList');
      const countLbl = document.getElementById('stockCountLabel');

      if (!data.items?.length) {
        list.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No matching stock records.</div>';
        if (countLbl) countLbl.textContent = '0 items';
        return;
      }

      if (countLbl) countLbl.textContent = `${data.items.length} items`;

      list.innerHTML = data.items.map(item => `
        <div class="acc-item">
          <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
            <div class="acc-trigger-left">
              ${riskBadge(item.risk_level)}
              <span class="acc-name">${item.ingredient_name}</span>
              <span class="acc-meta">${item.category} · ${item.storage_type}</span>
            </div>
            <div class="acc-trigger-right">
              <span style="font-size:0.82rem;font-weight:600;color:var(--text-1);">${item.closing_stock_qty} ${item.unit}</span>
              <span style="font-size:0.75rem;color:var(--text-3);">${item.min_days_to_expiry}d left</span>
              ${buildChevron()}
            </div>
          </button>
          <div class="acc-body">
            <div class="acc-detail-grid">
              <div class="acc-detail-item"><div class="acc-detail-label">Stock</div><div class="acc-detail-value">${item.closing_stock_qty} ${item.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Unit Cost</div><div class="acc-detail-value">₹${item.unit_cost_inr.toFixed(2)}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Min Expiry</div><div class="acc-detail-value ${item.min_days_to_expiry<=2?'danger':item.min_days_to_expiry<=5?'warn':''}">${item.min_days_to_expiry} days</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">7d Usage</div><div class="acc-detail-value">${item.usage_7d_mean}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Cover Days</div><div class="acc-detail-value">${item.cover_days}d</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Risk Prob</div><div class="acc-detail-value">${Math.round(item.risk_prob_next_3d*100)}%</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Exposure</div><div class="acc-detail-value ${item.financial_exposure_inr>0?'danger':''}">₹${item.financial_exposure_inr.toFixed(2)}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">ID</div><div class="acc-detail-value" style="color:var(--text-3);">${item.ingredient_id}</div></div>
            </div>
            <div class="acc-body-actions">
              <button class="btn btn-outline btn-sm" onclick="app.quickAddStockPrompt('${item.ingredient_id}','${item.ingredient_name}')">+ Add Stock</button>
            </div>
          </div>
        </div>`).join('');
    } catch(e) { console.error('Inventory:', e); }
  }

  // ── FORECAST ──────────────────────────────────────────────────────────
  async loadForecasts() {
    try {
      const cat = document.getElementById('forecastCategoryFilter')?.value || 'all';
      let url   = `/api/v1/forecasts?restaurant_id=${this.selectedRestaurant}`;
      if (cat !== 'all') url += `&category=${cat}`;

      const data = await fetch(url).then(r=>r.json());
      const list = document.getElementById('forecastAccList');

      if (!data.forecasts?.length) {
        list.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No forecasts found.</div>';
        return;
      }

      const confBadge = c => c === 'High' ? 'badge-dark' : 'badge-neutral';

      list.innerHTML = data.forecasts.map(d => `
        <div class="acc-item">
          <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
            <div class="acc-trigger-left">
              <span class="acc-name">${d.dish_name}</span>
              <span class="acc-meta">${d.category}</span>
            </div>
            <div class="acc-trigger-right">
              <span style="font-size:0.88rem;font-weight:700;color:var(--text-1);">${d.predicted_orders_median}</span>
              <span class="badge ${confBadge(d.forecast_confidence)}">${d.forecast_confidence}</span>
              ${buildChevron()}
            </div>
          </button>
          <div class="acc-body">
            <div class="acc-detail-grid">
              <div class="acc-detail-item"><div class="acc-detail-label">Median Orders</div><div class="acc-detail-value">${d.predicted_orders_median}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Lower 80%</div><div class="acc-detail-value">${d.lower_80}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Upper 80%</div><div class="acc-detail-value">${d.upper_80}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Suggested Prep</div><div class="acc-detail-value">${d.suggested_prep_qty} units</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Cook Now (Batch 1)</div><div class="acc-detail-value">${d.prep_stage_batch_qty} units</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Portion Cost</div><div class="acc-detail-value">₹${d.cost_per_portion_inr.toFixed(2)}</div></div>
            </div>
          </div>
        </div>`).join('');
    } catch(e) { console.error('Forecasts:', e); }
  }

  async loadPurchasePlan() {
    try {
      const data = await fetch(`/api/v1/plans/purchases?restaurant_id=${this.selectedRestaurant}`).then(r=>r.json());
      const list  = document.getElementById('purchasePlanAccList');
      const badge = document.getElementById('totalPurchaseValueBadge');

      if (badge) badge.textContent = `Total: ₹${(data.total_value_inr||0).toLocaleString(undefined,{minimumFractionDigits:2})}`;

      if (!data.purchases?.length) {
        list.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No purchases required — stock covers demand.</div>';
        return;
      }

      list.innerHTML = data.purchases.map(p => `
        <div class="acc-item">
          <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
            <div class="acc-trigger-left">
              <span class="acc-name">${p.ingredient_name}</span>
              <span class="acc-meta">${p.recommended_purchase_qty} ${p.unit} needed</span>
            </div>
            <div class="acc-trigger-right">
              <span style="font-size:0.82rem;font-weight:700;color:var(--text-1);">₹${p.purchase_value_inr.toFixed(2)}</span>
              ${buildChevron()}
            </div>
          </button>
          <div class="acc-body">
            <div class="acc-detail-grid">
              <div class="acc-detail-item"><div class="acc-detail-label">Required Qty</div><div class="acc-detail-value">${p.required_qty} ${p.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Usable Stock</div><div class="acc-detail-value">${p.usable_stock_qty} ${p.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Incoming</div><div class="acc-detail-value">${p.incoming_qty} ${p.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Recommended Buy</div><div class="acc-detail-value">${p.recommended_purchase_qty} ${p.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Est. Value</div><div class="acc-detail-value">₹${p.purchase_value_inr.toFixed(2)}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Surplus Adj.</div><div class="acc-detail-value">${p.purchase_adjustment_qty>0?`-${p.purchase_adjustment_qty} ${p.unit}`:'None'}</div></div>
            </div>
          </div>
        </div>`).join('');
    } catch(e) { console.error('Purchase plan:', e); }
  }

  toggleSimulator() {
    const card = document.getElementById('simulatorCard');
    if (!card) return;
    const isHidden = card.style.display === 'none';
    card.style.display = isHidden ? 'block' : 'none';
    if (isHidden) card.scrollIntoView({ behavior:'smooth' });
  }

  async runDemandSimulator() {
    const btn = document.getElementById('btnRunSimulator');
    btn.textContent = 'Calculating…'; btn.disabled = true;
    try {
      const payload = {
        restaurant_id: document.getElementById('simRestId').value,
        dish_id: document.getElementById('simDishId').value,
        target_date: document.getElementById('simDate').value || '2026-01-01',
        selling_price_inr: parseFloat(document.getElementById('simPrice').value) || null,
        promo_flag: document.getElementById('simPromo').checked ? 1 : 0,
        holiday_flag: document.getElementById('simHoliday').checked ? 1 : 0,
        avg_temp_c: parseFloat(document.getElementById('simTemp').value) || 24.0,
        rainfall_mm: parseFloat(document.getElementById('simRain').value) || 0.0,
      };
      const data = await fetch('/api/v1/predict/demand', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
      }).then(r=>r.json());

      const box = document.getElementById('simResultBox');
      box.style.display = 'block';
      document.getElementById('simResultDishName').textContent   = `${data.dish_name} (${data.category})`;
      document.getElementById('simResultConfidence').textContent = `${data.forecast_confidence} Confidence`;
      document.getElementById('simResultMedian').textContent     = data.predicted_orders_median;
      document.getElementById('simResultRange').textContent      = `${data.lower_80} – ${data.upper_80}`;
      document.getElementById('simResultPrep').textContent       = `${data.suggested_prep_qty} units`;
      document.getElementById('simResultBatch').textContent      = `${data.prep_stage_batch_qty} units`;
      this.showToast(`Prediction: ${data.predicted_orders_median} orders`);
    } catch(e) {
      this.showToast('Prediction error: ' + e.message);
    } finally {
      btn.textContent = 'Run Prediction'; btn.disabled = false;
    }
  }

  // ── ACTIONS ───────────────────────────────────────────────────────────
  async loadActions() {
    try {
      const type   = document.getElementById('actionTypeFilter')?.value   || 'all';
      const status = document.getElementById('actionStatusFilter')?.value || 'all';
      let url = `/api/v1/actions?restaurant_id=${this.selectedRestaurant}`;
      if (type   !== 'all') url += `&type=${type}`;
      if (status !== 'all') url += `&status=${status}`;

      const data = await fetch(url).then(r=>r.json());

      document.getElementById('actionsPendingCount').textContent   = data.pending_count || 0;
      document.getElementById('actionsCompletedCount').textContent = data.completed_count || 0;
      document.getElementById('actionsCapturedSavings').textContent = `₹${(data.captured_savings_inr||0).toLocaleString(undefined,{minimumFractionDigits:2})}`;

      const badge = document.getElementById('pendingActionsBadge');
      if (badge) badge.textContent = data.pending_count || 0;
      const mobBadge = document.getElementById('mobilePendingBadge');
      if (mobBadge) mobBadge.textContent = data.pending_count || 0;

      const container = document.getElementById('actionsContainer');
      if (!data.actions?.length) {
        container.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No actions matching filters.</div>';
        return;
      }

      const dotClass = s => ({ pending:'dot-pending', completed:'dot-completed', deferred:'dot-deferred', dismissed:'dot-dismissed' })[s] || 'dot-pending';
      const typeLabel = t => t.replace(/_/g,' ');

      container.innerHTML = data.actions.map(act => `
        <div class="acc-item ${act.status==='completed'?'':''}">
          <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))" style="opacity:${['dismissed','completed'].includes(act.status)?0.6:1};">
            <div class="acc-trigger-left">
              <span class="action-status-dot ${dotClass(act.status)}"></span>
              <div style="min-width:0;">
                <div class="acc-name">${act.action}</div>
                <div class="acc-meta">${typeLabel(act.type)} · ${act.status.toUpperCase()}</div>
              </div>
            </div>
            <div class="acc-trigger-right">
              <span style="font-size:0.88rem;font-weight:700;color:var(--danger);">₹${act.avoidable_cost_inr.toFixed(0)}</span>
              ${buildChevron()}
            </div>
          </button>
          <div class="acc-body">
            <div class="acc-detail-grid">
              <div class="acc-detail-item"><div class="acc-detail-label">Why</div><div class="acc-detail-value" style="white-space:normal;font-size:0.82rem;">${act.why}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Avoidable Cost</div><div class="acc-detail-value danger">₹${act.avoidable_cost_inr.toFixed(2)}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Feasibility</div><div class="acc-detail-value">${Math.round(act.feasibility*100)}%</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Status</div><div class="acc-detail-value">${act.status}</div></div>
            </div>
            <div class="acc-body-actions">
              ${act.status!=='completed' ? `<button class="btn btn-primary btn-sm" onclick="app.updateActionStatus(${act.id},'completed')">Mark Done</button>` : ''}
              ${act.status==='pending' ? `<button class="btn btn-outline btn-sm" onclick="app.updateActionStatus(${act.id},'deferred')">Defer</button>
                <button class="btn btn-outline btn-sm" onclick="app.updateActionStatus(${act.id},'dismissed')">Dismiss</button>` : ''}
              ${act.status!=='pending' ? `<button class="btn btn-outline btn-sm" onclick="app.updateActionStatus(${act.id},'pending')">Reopen</button>` : ''}
            </div>
          </div>
        </div>`).join('');
    } catch(e) { console.error('Actions:', e); }
  }

  async updateActionStatus(id, status) {
    try {
      await fetch(`/api/v1/actions/${id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})
      });
      this.showToast(`Action → ${status}`);
      this.loadActions();
      this.loadReportSummary();
    } catch(e) { this.showToast('Error: ' + e.message); }
  }

  async resetActions() {
    if (!confirm('Reset all recommendations to pending?')) return;
    try {
      await fetch('/api/v1/actions/reset', { method:'POST' });
      this.showToast('All reset to pending');
      this.loadActions();
      this.loadReportSummary();
    } catch(e) { this.showToast('Error: ' + e.message); }
  }

  // ── ANALYTICS ─────────────────────────────────────────────────────────
  async loadAnalytics() {
    try {
      // Waste by reason
      const wData = await fetch(`/api/v1/analytics/waste-by-reason?restaurant_id=${this.selectedRestaurant}`).then(r=>r.json());
      const totalLbl = document.getElementById('totalWasteCostLabel');
      if (totalLbl) totalLbl.textContent = `Total: ₹${(wData.total_waste_cost_inr||0).toLocaleString(undefined,{minimumFractionDigits:2})}`;

      const reasonNames = { expired:'Batch Expiry', spoilage:'Storage Spoilage', 'over-prep':'Over-Preparation' };
      const reasonBox = document.getElementById('wasteReasonContainer');
      reasonBox.innerHTML = (wData.breakdown||[]).map(item => `
        <div class="progress-item">
          <div class="progress-meta">
            <span class="progress-label">${reasonNames[item.reason]||item.reason}</span>
            <span class="progress-value">₹${item.total_cost_inr.toLocaleString()} (${item.pct_of_total}%)</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:${item.pct_of_total}%;"></div></div>
          <div style="font-size:0.7rem;color:var(--text-4);margin-top:0.2rem;">${item.event_count} events · ${item.total_qty} units</div>
        </div>`).join('') || '<div style="color:var(--text-3);font-size:0.82rem;">No data.</div>';

      // Top wasted ingredients (accordion)
      const ingData = await fetch(`/api/v1/analytics/waste-by-ingredient?restaurant_id=${this.selectedRestaurant}&limit=8`).then(r=>r.json());
      const ingList  = document.getElementById('wasteIngAccList');
      ingList.innerHTML = (ingData.items||[]).map(item => `
        <div class="acc-item">
          <button class="acc-trigger" onclick="toggleAcc(this.closest('.acc-item'))">
            <div class="acc-trigger-left">
              <span class="acc-name">${item.ingredient_name}</span>
            </div>
            <div class="acc-trigger-right">
              <span style="font-size:0.82rem;font-weight:700;color:var(--danger);">₹${item.total_cost_inr.toLocaleString()}</span>
              ${buildChevron()}
            </div>
          </button>
          <div class="acc-body">
            <div class="acc-detail-grid">
              <div class="acc-detail-item"><div class="acc-detail-label">Total Discarded</div><div class="acc-detail-value">${item.total_qty} ${item.unit}</div></div>
              <div class="acc-detail-item"><div class="acc-detail-label">Total Cost</div><div class="acc-detail-value danger">₹${item.total_cost_inr.toLocaleString()}</div></div>
            </div>
          </div>
        </div>`).join('') || '<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:0.82rem;">No data.</div>';

      // Demand trend
      const hData = await fetch(`/api/v1/analytics/historical-demand?restaurant_id=${this.selectedRestaurant}&days=30`).then(r=>r.json());
      const chartBox = document.getElementById('demandTrendChart');
      const history  = hData.history || [];
      const maxU = Math.max(...history.map(h=>h.total_units), 100);
      chartBox.innerHTML = history.map(day => {
        const hPct = Math.round(day.total_units / maxU * 100);
        return `<div class="trend-col" title="${day.date}: ${day.total_units} orders">
          <div class="trend-bar" style="height:${hPct}%;"></div>
          <div class="trend-date">${day.date.slice(5)}</div>
        </div>`;
      }).join('') || '<div style="color:var(--text-3);font-size:0.82rem;text-align:center;width:100%;">No history.</div>';

    } catch(e) { console.error('Analytics:', e); }
  }

  // ── RUN DAILY ANALYSIS ────────────────────────────────────────────────
  async runDailyAnalysis() {
    const btn = document.getElementById('btnRunAnalysis');
    const orig = btn.innerHTML;
    btn.innerHTML = '<span style="display:inline-block;width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;"></span> Running…';
    btn.disabled = true;
    try {
      await fetch('/api/v1/reports/generate?planning_date=2026-01-01', { method:'POST' });
      this.showToast('Daily report regenerated!');
      this.refreshCurrentView();
    } catch(e) {
      this.showToast('Error: ' + e.message);
    } finally {
      btn.innerHTML = orig;
      btn.disabled = false;
    }
  }

  // ── MODALS ────────────────────────────────────────────────────────────
  openModal(id)  { const m = document.getElementById(id); if(m) m.style.display='flex'; }
  closeModal(id) { const m = document.getElementById(id); if(m) m.style.display='none'; }
  quickAddStockPrompt(ingId, name) {
    this.openModal('modalAddStock');
    const sel = document.getElementById('modalAddStockIng');
    if (sel) sel.value = ingId;
  }

  async submitAddStock() {
    try {
      const qty = parseFloat(document.getElementById('modalAddStockQty').value) || 0;
      if (qty <= 0) { alert('Enter a valid quantity.'); return; }
      const expVal = document.getElementById('modalAddStockExp').value;
      const res = await fetch('/api/v1/inventory/stock', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          restaurant_id: document.getElementById('modalAddStockRest').value,
          ingredient_id: document.getElementById('modalAddStockIng').value,
          qty_added: qty,
          min_days_to_expiry: expVal ? parseFloat(expVal) : null,
        })
      });
      if (!res.ok) throw new Error('Failed to add stock');
      this.closeModal('modalAddStock');
      this.showToast('Stock added!');
      this.loadInventory();
      this.loadReportSummary();
    } catch(e) { alert('Error: ' + e.message); }
  }

  async submitRecordWaste() {
    try {
      const qty = parseFloat(document.getElementById('modalWasteQty').value) || 0;
      if (qty <= 0) { alert('Enter a valid quantity.'); return; }
      const res = await fetch('/api/v1/inventory/waste', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          restaurant_id: document.getElementById('modalWasteRest').value,
          ingredient_id: document.getElementById('modalWasteIng').value,
          qty,
          reason: document.getElementById('modalWasteReason').value,
          notes:  document.getElementById('modalWasteNotes').value,
        })
      });
      if (!res.ok) throw new Error('Failed to log waste');
      this.closeModal('modalRecordWaste');
      this.showToast('Waste logged!');
      this.loadInventory();
      this.loadReportSummary();
      if (this.currentTab === 'analytics') this.loadAnalytics();
    } catch(e) { alert('Error: ' + e.message); }
  }

  // ── TOAST ─────────────────────────────────────────────────────────────
  showToast(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.style.display = 'block';
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { t.style.display = 'none'; }, 3500);
  }
}

// Spinner keyframes injected once
const spinStyle = document.createElement('style');
spinStyle.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
document.head.appendChild(spinStyle);

let app;
window.addEventListener('DOMContentLoaded', () => { 
  app = new FreshFlowApp(); 
  window.app = app; 
});

// ─── MULTI-VIEW ROUTER & ONBOARDING CONTROLLER ───────────────────────────
const KITCHEN_PROFILES = {
  hotel: {
    name: 'Hotel & Resort Dining',
    short: 'Hotel & Resort',
    role: 'Executive Chef & Banquet Manager',
    icon: 'hotel'
  },
  restaurant: {
    name: 'Restaurant & Dine-In',
    short: 'Restaurant',
    role: 'Head Chef & General Manager',
    icon: 'restaurant'
  },
  hostelmess: {
    name: 'Hostel Mess & Institutional',
    short: 'Hostel Mess',
    role: 'Mess Supervisor & Food Committee',
    icon: 'corporate_fare'
  },
  cloudkitchen: {
    name: 'Cloud Kitchen & Dark Kitchen',
    short: 'Cloud Kitchen',
    role: 'Delivery Operations Lead',
    icon: 'cloud_queue'
  },
  cafebakery: {
    name: 'Cafe, Bakery & Patisserie',
    short: 'Bakery & Cafe',
    role: 'Head Pastry Chef & Roaster',
    icon: 'bakery_dining'
  }
};

let currentKitchenType = localStorage.getItem('freshflow_kitchen_type') || 'restaurant';

window.navigateToView = function(viewName) {
  document.querySelectorAll('.app-view').forEach(view => {
    view.classList.remove('active');
  });

  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) {
    targetView.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // If entering app, ensure FreshFlowApp refreshes its reveal elements and current tab
  if (viewName === 'app') {
    if (window.app) {
      window.app.switchTab(window.app.currentTab || 'home');
      observeRevealEls();
    }
  }
};

window.selectKitchenType = function(typeKey) {
  currentKitchenType = typeKey;
  localStorage.setItem('freshflow_kitchen_type', typeKey);

  // Update selection UI in onboarding cards
  document.querySelectorAll('.kitchen-card').forEach(card => {
    const cardType = card.getAttribute('data-kitchen');
    card.classList.toggle('selected', cardType === typeKey);
  });

  // Update label on login page
  const profile = KITCHEN_PROFILES[typeKey] || KITCHEN_PROFILES.restaurant;
  const loginLabel = document.getElementById('loginKitchenLabel');
  if (loginLabel) loginLabel.textContent = profile.name;

  // Update labels in workspace navbar & sidebar
  const navName = document.getElementById('navbarKitchenName');
  const navIcon = document.getElementById('navbarKitchenIcon');
  if (navName) navName.textContent = profile.short;
  if (navIcon) navIcon.textContent = profile.icon;

  const sideName = document.getElementById('sidebarProfileName');
  const sideRole = document.getElementById('sidebarProfileRole');
  if (sideName) sideName.textContent = profile.name;
  if (sideRole) sideRole.textContent = profile.role;
};

window.fillDemoCredentials = function() {
  const emailInput = document.getElementById('loginEmail');
  const passInput = document.getElementById('loginPassword');
  if (emailInput) emailInput.value = 'admin@freshflow.ai';
  if (passInput) passInput.value = 'freshflow2026';
  if (window.app && window.app.showToast) {
    window.app.showToast('✓ Demo credentials filled!');
  }
};

window.handleLoginSubmit = function(e) {
  if (e) e.preventDefault();
  if (window.app && window.app.showToast) {
    window.app.showToast('✓ Signed in successfully! Launching workspace...');
  }
  window.navigateToView('app');
};

window.quickDemoLogin = function() {
  window.navigateToView('app');
  if (window.app && window.app.showToast) {
    window.app.showToast('✓ Loaded workspace in Live Demo mode');
  }
};

// ─── SIDEBAR COLLAPSE TOGGLE ─────────────────────────────────────────────
window.toggleSidebar = function() {
  const sidebar = document.getElementById('appSidebar');
  const toggleIcon = document.getElementById('sidebarToggleIcon');
  const miniIcon = document.getElementById('sidebarMiniIcon');
  if (!sidebar) return;

  const isCollapsed = sidebar.classList.toggle('collapsed');
  localStorage.setItem('freshflow_sidebar_collapsed', isCollapsed ? '1' : '0');

  if (toggleIcon) {
    toggleIcon.textContent = isCollapsed ? 'menu' : 'menu_open';
  }
  if (miniIcon) {
    miniIcon.textContent = isCollapsed ? 'chevron_right' : 'chevron_left';
  }
};

// Restore saved sidebar collapsed state and kitchen type on page load
window.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('freshflow_sidebar_collapsed') === '1') {
    const sidebar = document.getElementById('appSidebar');
    if (sidebar) sidebar.classList.add('collapsed');
    const toggleIcon = document.getElementById('sidebarToggleIcon');
    const miniIcon = document.getElementById('sidebarMiniIcon');
    if (toggleIcon) toggleIcon.textContent = 'menu';
    if (miniIcon) miniIcon.textContent = 'chevron_right';
  }

  // Restore kitchen type
  window.selectKitchenType(currentKitchenType);
});

// ─── VIDEO LOADING SCREEN CONTROLLER ──────────────────────────
window.triggerAppLaunch = function() {
  const screen = document.getElementById('appLaunchScreen');
  if (!screen) return;

  const video = document.getElementById('launchVideo');
  screen.classList.remove('launch-complete');
  screen.style.display = 'flex';

  let dismissed = false;
  const finishLaunch = function() {
    if (dismissed) return;
    dismissed = true;
    screen.classList.add('launch-complete');
    setTimeout(() => {
      screen.style.display = 'none';
    }, 650);
  };

  window.dismissLaunchScreen = finishLaunch;

  if (video) {
    try {
      video.currentTime = 0;
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => console.warn('Autoplay restricted:', err));
      }
    } catch (e) {
      console.warn('Video error:', e);
    }
    video.addEventListener('ended', finishLaunch, { once: true });
    setTimeout(finishLaunch, 4300);
  } else {
    setTimeout(finishLaunch, 1500);
  }
};

window.addEventListener('DOMContentLoaded', () => {
  window.triggerAppLaunch();
});

