let isRunning = false;
let pollingInterval = null;
let isFetchingState = false;

async function fetchState() {
  if (isFetchingState) return;
  isFetchingState = true;
  try {
    const res = await fetch("/api/state");
    if (!res.ok) return;
    const data = await res.json();
    updateUI(data);
  } catch (err) {
    console.error("State alma hatası:", err);
  } finally {
    isFetchingState = false;
  }
}

let currentMode = "simulation";
let isActionPending = false;

function updateUI(data) {
  isRunning = data.is_running;
  currentMode = data.mode || "simulation";
  const isLive = currentMode === "live";

  // Durum Rozetleri ve Buton Durumları
  const statusBadge = document.getElementById("status-badge");
  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");

  if (!isActionPending) {
    if (isRunning) {
      if (statusBadge) {
        statusBadge.className = "badge badge-running";
        statusBadge.innerHTML = isLive 
          ? '<span class="badge-pulse"></span> CANLI İŞLEMDE (BOT AKTİF)'
          : '<span class="badge-pulse"></span> ÇALIŞIYOR (TEST AKTİF)';
      }
      if (btnStart) {
        btnStart.disabled = true;
        btnStart.innerHTML = isLive ? "▶️ Canlı Al-Sat Çalışıyor" : "▶️ Test Çalışıyor";
      }
      if (btnStop) {
        btnStop.disabled = false;
        btnStop.innerHTML = isLive ? "⏹️ Botu Durdur (Çıkış Yap)" : "⏹️ Testi Durdur & Rapor Al";
      }
    } else {
      if (statusBadge) {
        statusBadge.className = "badge badge-stopped";
        statusBadge.innerHTML = '<span class="badge-pulse"></span> BEKLEMEDE';
      }
      if (btnStart) {
        btnStart.disabled = false;
        btnStart.innerHTML = isLive ? "▶️ Canlı Al-Satı Başlat" : "▶️ Testi Başlat";
      }
      if (btnStop) {
        btnStop.disabled = true;
        btnStop.innerHTML = isLive ? "⏹️ Bot Durduruldu" : "⏹️ Test Durduruldu";
      }
    }
  }

  // Arayüz başlık metinlerini moda göre uyarla
  const lblSubTitle = document.getElementById("lbl-sub-title");
  const lblDuration = document.getElementById("lbl-duration");
  const lblReportsTitle = document.getElementById("lbl-reports-title");

  if (isLive) {
    if (lblSubTitle) lblSubTitle.innerText = "Binance TR Gerçek Hesap ile Otonom Al-Sat & Canlı Risk Yönetimi";
    if (lblDuration) lblDuration.innerText = "Çalışma Süresi (Dakika)";
    if (lblReportsTitle) lblReportsTitle.innerText = "📁 İşlem & Performans Raporları";
  } else {
    if (lblSubTitle) lblSubTitle.innerText = "Sanal Bütçe ile Canlı Piyasa Testi & Otomatik Optimizasyon";
    if (lblDuration) lblDuration.innerText = "Test Süresi (Dakika)";
    if (lblReportsTitle) lblReportsTitle.innerText = "📁 Kayıtlı Test Raporları";
  }

  // Durum Metni ve Canlı Nabız
  const statusTextElem = document.getElementById("live-status-text");
  const scanPulse = document.getElementById("scan-pulse-badge");
  if (statusTextElem && data.status_text) {
    statusTextElem.innerText = data.status_text;
  }
  if (scanPulse) {
    if (isRunning) {
      scanPulse.className = "badge badge-running";
      scanPulse.innerHTML = '<span class="badge-pulse"></span> CANLI TARAMA AKTİF';
    } else {
      scanPulse.className = "badge badge-stopped";
      scanPulse.innerHTML = '<span class="badge-pulse"></span> BEKLEMEDE';
    }
  }

  // Geri Sayım Sayacı
  const timerBox = document.getElementById("timer-display");
  if (isRunning && data.remaining_seconds !== undefined) {
    const mins = Math.floor(data.remaining_seconds / 60);
    const secs = data.remaining_seconds % 60;
    timerBox.innerText = `⏱️ Kalan: ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  } else {
    timerBox.innerText = `⏱️ Süre: ${data.session_duration_minutes || 15} dk`;
  }

  // Piyasa Radarı Coinleri
  const radarContainer = document.getElementById("radar-coins-list");
  if (radarContainer && data.radar_top_coins && data.radar_top_coins.length > 0) {
    radarContainer.innerHTML = data.radar_top_coins.map(c => {
      const chgColor = c.change_pct >= 0 ? "var(--success)" : "var(--danger)";
      const sign = c.change_pct > 0 ? "+" : "";
      const obs = c.observation || {};
      let obsHtml = "";
      if (obs.status === "cooling_down") {
        obsHtml = `<span class="badge" style="background: rgba(156,163,175,0.15); color: #9ca3af; font-size: 10px; border: 1px solid rgba(156,163,175,0.3);">⏳ Dinlenme (${obs.cooldown_remaining || 0}s)</span>`;
      } else if (obs.elapsed !== undefined && obs.elapsed > 0) {
        const burstStr = obs.min_burst_count > 1 ? ` (💥${obs.burst_count || 0}/${obs.min_burst_count})` : "";
        if (obs.is_ready) {
          obsHtml = `<span class="badge" style="background: rgba(16,185,129,0.18); color: var(--success); font-size: 10px; border: 1px solid rgba(16,185,129,0.3);">🚀 Çifte Patlama (%+${obs.change_pct})</span>`;
        } else {
          obsHtml = `<span class="badge" style="background: rgba(59,130,246,0.18); color: #60a5fa; font-size: 10px; border: 1px solid rgba(59,130,246,0.3);">👁️ ${obs.elapsed}/${obs.min_sec || 45}s${burstStr}</span>`;
        }
      }
      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--card-border); font-size: 12px;">
          <div>
            <strong style="color: #fff;">${c.symbol}</strong>
            <span style="color: var(--text-muted); font-size: 11px; margin-left: 6px;">${c.price < 1 ? c.price.toFixed(6) : c.price.toFixed(4)} TL</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${obsHtml}
            <span style="color: ${chgColor}; font-weight: bold;">${sign}${c.change_pct.toFixed(2)}%</span>
            <button type="button" class="badge" style="cursor: pointer; background: rgba(245,158,11,0.15); color: var(--accent); border: 1px solid rgba(245,158,11,0.3); font-size: 10px; padding: 2px 8px;" onclick="selectRadarCoin('${c.symbol}')">Seç</button>
          </div>
        </div>
      `;
    }).join("");
  }

  const obsInput = document.getElementById("input-obs-seconds");
  if (obsInput && data.config && data.config.candidate_observation_seconds !== undefined && document.activeElement !== obsInput) {
    obsInput.value = data.config.candidate_observation_seconds;
  }

  const trailingActInput = document.getElementById("input-trailing-act");
  if (trailingActInput && data.config && data.config.trailing_activation_pct !== undefined && document.activeElement !== trailingActInput) {
    trailingActInput.value = data.config.trailing_activation_pct;
  }

  const onlyUptrendCheck = document.getElementById("check-only-uptrend");
  if (onlyUptrendCheck && data.config && data.config.only_uptrend !== undefined && document.activeElement !== onlyUptrendCheck) {
    onlyUptrendCheck.checked = data.config.only_uptrend;
  }

  // Otomatik Coin Seçimi Durumu
  const autoCoinCheck = document.getElementById("check-auto-coin");
  const symbolInput = document.getElementById("input-symbol");
  const symbolGroup = document.getElementById("symbol-group");
  if (data.config && data.config.auto_select_coin !== undefined && autoCoinCheck) {
    if (document.activeElement !== autoCoinCheck) {
      autoCoinCheck.checked = data.config.auto_select_coin;
    }
    if (autoCoinCheck.checked) {
      symbolInput.disabled = true;
      symbolInput.value = "AUTO (Radar Aktif)";
      if (symbolGroup) symbolGroup.style.opacity = "0.6";
    } else {
      symbolInput.disabled = false;
      if (symbolInput.value.includes("AUTO")) symbolInput.value = data.symbol || "SOL_TRY";
      if (symbolGroup) symbolGroup.style.opacity = "1";
    }
  }

  // Piyasa Verileri
  const m = data.market || {};
  if (m.price) {
    document.getElementById("val-price").innerText = `${m.price.toFixed(4)} TL`;
    document.getElementById("sub-symbol").innerText = `${data.symbol} | Alış: ${m.bid?.toFixed(4)} / Satış: ${m.ask?.toFixed(4)}`;
    document.getElementById("ind-rsi").innerText = m.rsi !== undefined ? m.rsi : "-";
    document.getElementById("ind-bb-upper").innerText = m.bb_upper ? m.bb_upper.toFixed(4) : "-";
    document.getElementById("ind-bb-lower").innerText = m.bb_lower ? m.bb_lower.toFixed(4) : "-";
    if (document.getElementById("ind-adx")) document.getElementById("ind-adx").innerText = m.adx !== undefined ? m.adx : "-";
    document.getElementById("ind-spread").innerText = m.spread_pct !== undefined ? `%${m.spread_pct.toFixed(3)}` : "-";
  }

  // Piyasa Rejimi Rozeti
  const regimeBadge = document.getElementById("badge-regime");
  if (regimeBadge && data.current_regime) {
    const reg = data.current_regime;
    if (reg === "BULLISH_TREND") {
      regimeBadge.innerText = "🚀 Rejim: GÜÇLÜ TREND";
      regimeBadge.style.background = "rgba(16, 185, 129, 0.2)";
      regimeBadge.style.color = "var(--success)";
      regimeBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
    } else if (reg === "DEFENSIVE_DUMP") {
      regimeBadge.innerText = "🛑 Rejim: SAVUNMA / DÜŞÜŞ";
      regimeBadge.style.background = "rgba(239, 68, 68, 0.2)";
      regimeBadge.style.color = "var(--danger)";
      regimeBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
    } else {
      regimeBadge.innerText = "🔄 Rejim: YATAY KANAL";
      regimeBadge.style.background = "rgba(59, 130, 246, 0.2)";
      regimeBadge.style.color = "#60a5fa";
      regimeBadge.style.borderColor = "rgba(59, 130, 246, 0.4)";
    }
  }

  // Mod Rozeti ve Başlığı (Canlı vs Sanal)
  const modeBadge = document.getElementById("badge-mode");
  const equityTitle = document.getElementById("lbl-equity-title");
  if (isLive) {
    if (modeBadge) {
      modeBadge.innerText = "🔥 MOD: GERÇEK HESAP (CANLI)";
      modeBadge.style.background = "rgba(239, 68, 68, 0.2)";
      modeBadge.style.color = "#f87171";
      modeBadge.style.border = "1px solid rgba(239, 68, 68, 0.4)";
    }
    if (equityTitle) {
      equityTitle.innerText = "Gerçek Portföy Değeri";
    }
  } else {
    if (modeBadge) {
      modeBadge.innerText = "MOD: SANAL PARA (PAPER TRADING)";
      modeBadge.style.background = "rgba(245, 158, 11, 0.2)";
      modeBadge.style.color = "var(--accent)";
      modeBadge.style.border = "none";
    }
    if (equityTitle) {
      equityTitle.innerText = "Sanal Portföy Değeri";
    }
  }

  // Portföy Verileri
  const p = data.portfolio || {};
  if (p.total_equity !== undefined) {
    document.getElementById("val-equity").innerText = `${p.total_equity.toFixed(2)} TL`;
    const cashPrefix = isLive ? "Gerçek Nakit (TRY)" : "Nakit";
    document.getElementById("sub-cash").innerText = `${cashPrefix}: ${p.cash.toFixed(2)} TL | Pozisyonda: ${p.invested_value.toFixed(2)} TL`;

    const pnlElem = document.getElementById("val-pnl");
    const pnlSign = p.total_pnl > 0 ? "+" : "";
    pnlElem.innerText = `${pnlSign}${p.total_pnl.toFixed(2)} TL (${pnlSign}${p.total_pnl_pct.toFixed(2)}%)`;
    pnlElem.style.color = p.total_pnl >= 0 ? "var(--success)" : "var(--danger)";

    document.getElementById("val-winrate").innerText = `%${p.win_rate || 0}`;
    document.getElementById("sub-trades-count").innerText = `${p.winning_trades || 0} Kazanç / ${p.losing_trades || 0} Kayıp (Toplam: ${p.total_trades || p.total_closed_trades || 0})`;
  }

  // Açık Pozisyonlar
  const posTable = document.getElementById("positions-body");
  const openPositions = p.open_positions || [];

  // Sepet Durumu Rozeti
  const targetCoins = (data.config && data.config.target_coins_count) || 5;
  const openCount = openPositions.length;
  const basketBadge = document.getElementById("badge-basket-status");
  if (basketBadge) {
    basketBadge.innerText = `${openCount} / ${targetCoins} Coin Dolu (Sürekli Rotasyon)`;
    if (openCount >= targetCoins) {
      basketBadge.style.background = "rgba(16, 185, 129, 0.15)";
      basketBadge.style.color = "var(--success)";
      basketBadge.style.borderColor = "rgba(16, 185, 129, 0.3)";
    } else {
      basketBadge.style.background = "rgba(59, 130, 246, 0.15)";
      basketBadge.style.color = "#60a5fa";
      basketBadge.style.borderColor = "rgba(59, 130, 246, 0.3)";
    }
  }

  const targetCoinsInput = document.getElementById("input-target-coins");
  if (targetCoinsInput && data.config && data.config.target_coins_count && document.activeElement !== targetCoinsInput) {
    targetCoinsInput.value = data.config.target_coins_count;
  }

  const budgetInput = document.getElementById("input-budget");
  if (budgetInput && data.config && data.config.budget_per_trade && document.activeElement !== budgetInput) {
    budgetInput.value = data.config.budget_per_trade;
  }

  if (openPositions.length === 0) {
    posTable.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-muted);">Açık pozisyon bulunmuyor</td></tr>';
  } else {
    posTable.innerHTML = openPositions.map(pos => {
      const pnlColor = pos.unrealized_pnl >= 0 ? "var(--success)" : "var(--danger)";
      const pnlSign = pos.unrealized_pnl > 0 ? "+" : "";
      const priceDecimals = pos.current_price < 1 ? 6 : 4;
      return `
        <tr>
          <td><strong>${pos.symbol}</strong></td>
          <td>${pos.entry_price.toFixed(priceDecimals)} TL</td>
          <td>${pos.current_price.toFixed(priceDecimals)} TL</td>
          <td>${pos.quantity.toFixed(4)}</td>
          <td style="color: ${pnlColor}; font-weight: bold;">${pnlSign}${pos.unrealized_pnl.toFixed(2)} TL (${pnlSign}${pos.unrealized_pnl_pct.toFixed(2)}%)</td>
          <td><span class="badge badge-running">AKTİF SEPET</span></td>
          <td style="text-align: right;">
            <button type="button" class="badge" style="cursor: pointer; background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.4); font-size: 11px; padding: 2px 8px; font-weight: 600;" onclick="closePosition('${pos.position_id}', '${pos.symbol}')">
              ❌ Sat
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // Tamamlanan İşlemler (Son işlem en üstte - Ters kronolojik)
  const tradesTable = document.getElementById("trades-body");
  const closedTrades = (p.closed_trades || []).slice().reverse();
  if (closedTrades.length === 0) {
    tradesTable.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">Henüz kapanmış işlem yok</td></tr>';
  } else {
    tradesTable.innerHTML = closedTrades.slice(0, 15).map(t => {
      const pnlColor = t.is_win ? "var(--success)" : "var(--danger)";
      const pnlSign = t.net_pnl > 0 ? "+" : "";
      const timeStr = t.timestamp ? new Date(t.timestamp * 1000).toLocaleTimeString() : "-";
      const entryP = typeof t.entry_price === "number" ? t.entry_price.toFixed(4) : t.entry_price;
      const exitP = typeof t.exit_price === "number" ? t.exit_price.toFixed(4) : t.exit_price;
      return `
        <tr>
          <td>${timeStr}</td>
          <td><strong>${t.symbol || '-'}</strong></td>
          <td>${entryP} TL</td>
          <td>${exitP} TL</td>
          <td style="color: ${pnlColor}; font-weight: bold;">${pnlSign}${t.net_pnl.toFixed(2)} TL (${pnlSign}${t.pnl_pct.toFixed(2)}%)</td>
          <td style="font-size: 11px; color: var(--text-muted);">${t.reason || '-'}</td>
        </tr>
      `;
    }).join("");
  }

  // Terminal Logları
  const terminal = document.getElementById("terminal");
  if (data.logs && data.logs.length > 0) {
    terminal.innerHTML = data.logs.map(log => {
      let cls = "terminal-line";
      if (log.includes("ALIŞ")) cls += " buy";
      else if (log.includes("Satış") || log.includes("KAPANIŞI")) cls += " sell";
      else if (log.includes("Hata") || log.includes("DURDURULDU")) cls += " alert";
      return `<div class="${cls}">${log}</div>`;
    }).join("");
    terminal.scrollTop = terminal.scrollHeight;
  }

  // Rapor butonu uyarısı
  if (data.last_report && (data.last_report.url || data.last_report.html)) {
    const reportBox = document.getElementById("report-alert");
    reportBox.style.display = "block";
    let reportUrl = data.last_report.url;
    if (!reportUrl) {
      const cleanName = data.last_report.filename || data.last_report.html.replace(/^.*[\\\/]/, '');
      reportUrl = `/reports/${cleanName}`;
    }
    document.getElementById("report-link").href = reportUrl;
  }
}

async function startBot() {
  if (isRunning || isActionPending) return;

  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const statusBadge = document.getElementById("status-badge");

  isActionPending = true;
  if (btnStart) {
    btnStart.disabled = true;
    btnStart.innerHTML = "⏳ Başlatılıyor...";
  }
  if (btnStop) {
    btnStop.disabled = true;
  }
  if (statusBadge) {
    statusBadge.className = "badge badge-running";
    statusBadge.innerHTML = '<span class="badge-pulse"></span> BAŞLATILIYOR...';
  }

  const duration = parseInt(document.getElementById("input-duration").value) || 15;
  const strategy = document.getElementById("select-strategy").value;
  const symbol = document.getElementById("input-symbol").value;
  const budget = parseFloat(document.getElementById("input-budget").value) || 50;
  const autoCoin = document.getElementById("check-auto-coin") ? document.getElementById("check-auto-coin").checked : true;
  const targetCoinsInput = document.getElementById("input-target-coins");
  const targetCoins = targetCoinsInput ? parseInt(targetCoinsInput.value) : 5;
  const obsInput = document.getElementById("input-obs-seconds");
  const obsSec = obsInput ? parseInt(obsInput.value) : 45;
  const trailingActInput = document.getElementById("input-trailing-act");
  const onlyUptrendCheck = document.getElementById("check-only-uptrend");

  try {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration_minutes: duration,
        strategy: strategy,
        symbol: symbol,
        budget_per_trade: budget,
        auto_select_coin: autoCoin,
        target_coins_count: targetCoins,
        candidate_observation_seconds: obsSec,
        take_profit_pct: parseFloat(document.getElementById("input-tp").value),
        stop_loss_pct: parseFloat(document.getElementById("input-sl").value),
        trailing_stop_pct: parseFloat(document.getElementById("input-trailing").value),
        trailing_activation_pct: trailingActInput ? parseFloat(trailingActInput.value) : 0.8,
        only_uptrend: onlyUptrendCheck ? onlyUptrendCheck.checked : true,
      })
    });
    if (res.ok) {
      await fetchState();
    }
  } catch (e) {
    alert("Bot başlatılamadı: " + e);
  } finally {
    isActionPending = false;
    await fetchState();
  }
}

async function stopBot() {
  if (!isRunning || isActionPending) return;

  const confirmMsg = currentMode === "live"
    ? "Canlı al-sat oturumunu durdurup performans raporu almak istiyor musunuz?"
    : "Testi durdurup performans raporu oluşturmak istiyor musunuz?";
  if (!confirm(confirmMsg)) return;

  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const statusBadge = document.getElementById("status-badge");

  isActionPending = true;
  if (btnStop) {
    btnStop.disabled = true;
    btnStop.innerHTML = "⏳ Durduruluyor...";
  }
  if (btnStart) {
    btnStart.disabled = true;
  }
  if (statusBadge) {
    statusBadge.className = "badge badge-stopped";
    statusBadge.innerHTML = '<span class="badge-pulse"></span> DURDURULUYOR...';
  }

  try {
    const res = await fetch("/api/stop", { method: "POST" });
    if (res.ok) {
      await fetchState();
      loadReportsList();
    }
  } catch (e) {
    alert("Durdurma hatası: " + e);
  } finally {
    isActionPending = false;
    await fetchState();
  }
}

async function selectRadarCoin(symbol) {
  const autoCoinCheck = document.getElementById("check-auto-coin");
  if (autoCoinCheck) autoCoinCheck.checked = false;
  const symInput = document.getElementById("input-symbol");
  if (symInput) {
    symInput.disabled = false;
    symInput.value = symbol;
  }
  await saveConfigParams();
  fetchState();
}

async function saveConfigParams() {
  const autoCoinCheck = document.getElementById("check-auto-coin");
  const isAuto = autoCoinCheck ? autoCoinCheck.checked : true;
  const symbolInput = document.getElementById("input-symbol");
  const symVal = isAuto ? "AUTO" : (symbolInput.value.includes("AUTO") ? "SOL_TRY" : symbolInput.value);
  const targetCoinsInput = document.getElementById("input-target-coins");
  const obsInput = document.getElementById("input-obs-seconds");
  const trailingActInput = document.getElementById("input-trailing-act");
  const onlyUptrendCheck = document.getElementById("check-only-uptrend");

  const payload = {
    take_profit_pct: parseFloat(document.getElementById("input-tp").value),
    stop_loss_pct: parseFloat(document.getElementById("input-sl").value),
    trailing_stop_pct: parseFloat(document.getElementById("input-trailing").value),
    trailing_activation_pct: trailingActInput ? parseFloat(trailingActInput.value) : 0.8,
    budget_per_trade: parseFloat(document.getElementById("input-budget").value),
    strategy: document.getElementById("select-strategy").value,
    symbol: symVal,
    auto_select_coin: isAuto,
    target_coins_count: targetCoinsInput ? parseInt(targetCoinsInput.value) : 5,
    candidate_observation_seconds: obsInput && obsInput.value !== "" ? parseInt(obsInput.value) : 45,
    only_uptrend: onlyUptrendCheck ? onlyUptrendCheck.checked : true,
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      console.log("Parametreler güncellendi");
    }
  } catch (e) {
    console.error("Parametre kaydetme hatası: " + e);
  }
}

async function loadReportsList() {
  try {
    const res = await fetch("/api/reports");
    if (!res.ok) return;
    const reports = await res.json();
    const container = document.getElementById("reports-list");
    if (reports.length === 0) {
      container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">Henüz kaydedilmiş rapor yok.</div>';
    } else {
      container.innerHTML = reports.slice(0, 5).map(r => `
        <div style="padding: 6px 0; border-bottom: 1px solid var(--card-border); font-size: 13px;">
          <a href="${r.path}" target="_blank" style="color: var(--accent); text-decoration: none; font-weight: 500;">
            📊 ${r.filename}
          </a>
        </div>
      `).join("");
    }
  } catch (e) {
    console.error("Rapor listesi alınamadı:", e);
  }
}


async function closePosition(positionId, symbol) {
  const isLive = currentMode === "live";
  const promptText = isLive 
    ? `[CANLI İŞLEM] ${symbol} pozisyonunu piyasa fiyatından hemen satmak istiyor musunuz?`
    : `${symbol} pozisyonunu kapatmak istiyor musunuz?`;
  if (!confirm(promptText)) return;

  try {
    const res = await fetch("/api/close_position", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ position_id: positionId })
    });
    const data = await res.json();
    if (res.ok) {
      fetchState();
    } else {
      alert("Pozisyon kapatılamadı: " + (data.message || "Bilinmeyen hata"));
    }
  } catch (err) {
    alert("Bağlantı hatası: " + err);
  }
}

async function closeAllPositions() {
  const isLive = currentMode === "live";
  const promptText = isLive
    ? "🚨 [DİKKAT - CANLI İŞLEM] Tüm açık pozisyonları piyasa fiyatından hemen satıp nakde geçmek istiyor musunuz?"
    : "Tüm açık pozisyonları kapatmak istiyor musunuz?";
  if (!confirm(promptText)) return;

  try {
    const res = await fetch("/api/close_all", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      fetchState();
    } else {
      alert("Pozisyonlar kapatılamadı: " + (data.message || "Bilinmeyen hata"));
    }
  } catch (err) {
    alert("Bağlantı hatası: " + err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  fetchState();
  loadReportsList();
  pollingInterval = setInterval(fetchState, 1200);

  document.getElementById("btn-start").addEventListener("click", startBot);
  document.getElementById("btn-stop").addEventListener("click", stopBot);
  document.getElementById("btn-save-config").addEventListener("click", saveConfigParams);

  // Hızlı Parite Butonları
  document.querySelectorAll(".btn-pair").forEach(btn => {
    btn.addEventListener("click", async () => {
      const sym = btn.getAttribute("data-symbol");
      const autoCoinCheck = document.getElementById("check-auto-coin");
      if (sym === "AUTO") {
        if (autoCoinCheck) autoCoinCheck.checked = true;
      } else {
        if (autoCoinCheck) autoCoinCheck.checked = false;
        document.getElementById("input-symbol").value = sym;
      }
      await saveConfigParams();
      fetchState();
    });
  });

  // Otomatik Coin Seçimi Toggle Dinleyicisi
  const autoCoinCheck = document.getElementById("check-auto-coin");
  if (autoCoinCheck) {
    autoCoinCheck.addEventListener("change", async () => {
      await saveConfigParams();
      fetchState();
    });
  }
});
