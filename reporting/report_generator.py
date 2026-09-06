import os
import json
import time
from typing import Dict, Any, List

class ReportGenerator:
    """
    Test oturumu tamamlandığında veya talep edildiğinde detaylı HTML ve JSON
    performans raporları oluşturur.
    """
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)

    def generate_report(
        self,
        config_data: Dict[str, Any],
        metrics: Dict[str, Any],
        closed_trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]],
        logs: List[str] = None,
        open_positions: List[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(self.reports_dir, f"test_run_{timestamp_str}.json")
        html_path = os.path.join(self.reports_dir, f"test_run_{timestamp_str}.html")

        full_data = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": config_data,
            "metrics": metrics,
            "trades": closed_trades,
            "open_positions": open_positions or [],
            "equity_curve": equity_curve,
            "logs": logs or [],
        }

        # 1. JSON Kaydı
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)

        # 2. HTML Raporu
        html_content = self._build_html(full_data)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        filename = f"test_run_{timestamp_str}.html"
        return {
            "json": json_path,
            "html": html_path,
            "filename": filename,
            "url": f"/reports/{filename}",
        }

    def _build_html(self, data: Dict[str, Any]) -> str:
        m = data["metrics"]
        cfg = data["config"]
        trades = data["trades"]
        open_positions = data.get("open_positions", [])
        logs = data.get("logs", [])
        pnl_color = "#10b981" if m["net_pnl"] >= 0 else "#ef4444"
        pnl_prefix = "+" if m["net_pnl"] > 0 else ""

        rows = []
        for t in trades:
            t_color = "#10b981" if t.get("is_win") else "#ef4444"
            t_sign = "+" if t["net_pnl"] > 0 else ""
            t_time = time.strftime("%H:%M:%S", time.localtime(t.get("timestamp", time.time())))
            rows.append(f"""
            <tr>
                <td>{t_time}</td>
                <td><strong>{t.get('symbol')}</strong></td>
                <td>{t.get('entry_price', 0):.4f}</td>
                <td>{t.get('exit_price', 0):.4f}</td>
                <td>{t.get('quantity', 0):.4f}</td>
                <td style="color: {t_color}; font-weight: bold;">{t_sign}{t.get('net_pnl', 0):.2f} TL ({t_sign}{t.get('pnl_pct', 0):.2f}%)</td>
                <td>{t.get('total_fees', 0):.2f} TL</td>
                <td><span class="badge">{t.get('reason', '')}</span></td>
            </tr>
            """)

        table_body = "\n".join(rows) if rows else "<tr><td colspan='8' style='text-align:center;'>Bu test sürecinde kapanan işlem bulunamadı.</td></tr>"

        # Açık Pozisyonlar Tablosu
        open_rows = []
        unrealized_total = 0.0
        for op in open_positions:
            unrealized = op.get("unrealized_pnl", 0.0)
            unrealized_pct = op.get("unrealized_pnl_pct", 0.0)
            unrealized_total += unrealized
            op_color = "#10b981" if unrealized >= 0 else "#ef4444"
            op_sign = "+" if unrealized > 0 else ""
            cost = op.get("cost", op.get("quantity", 0) * op.get("entry_price", 0))
            open_rows.append(f"""
            <tr>
                <td><strong>{op.get('symbol')}</strong></td>
                <td>{op.get('entry_price', 0):.4f} TL</td>
                <td>{op.get('current_price', op.get('entry_price', 0)):.4f} TL</td>
                <td>{op.get('quantity', 0):.4f} ({cost:.2f} TL)</td>
                <td style="color: {op_color}; font-weight: bold;">{op_sign}{unrealized:.2f} TL ({op_sign}{unrealized_pct:.2f}%)</td>
                <td><span class="badge" style="background: rgba(59, 130, 246, 0.15); color: var(--info);">{op.get('reason', 'Açık Takip')}</span></td>
            </tr>
            """)

        open_table_body = "\n".join(open_rows) if open_rows else "<tr><td colspan='6' style='text-align:center;'>Açık kalan pozisyon yok (Tüm pozisyonlar realize edildi).</td></tr>"

        # Log Satırlarını HTML İçin Biçimlendir
        log_html_items = []
        for idx, line in enumerate(logs):
            escaped_line = (
                line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            # Renklendirme kuralı
            item_class = "log-normal"
            if "🟢" in escaped_line or "Alış" in escaped_line or "Portföye Eklendi" in escaped_line:
                item_class = "log-buy"
            elif "🛑" in escaped_line or "Zarar Kes" in escaped_line or "STOP-LOSS" in escaped_line or "iptal edildi" in escaped_line:
                item_class = "log-stop"
            elif "🎯" in escaped_line or "Kâr Al" in escaped_line or "TAKE-PROFIT" in escaped_line or "Kâr devri" in escaped_line:
                item_class = "log-win"
            elif "🔍" in escaped_line or "QUANT RADARI" in escaped_line or "RADAR" in escaped_line:
                item_class = "log-radar"
            elif "⏳" in escaped_line or "KALİBRASYON" in escaped_line:
                item_class = "log-calib"
            elif "⚠️" in escaped_line or "Düşüş" in escaped_line:
                item_class = "log-warn"

            log_html_items.append(f'<div class="log-entry {item_class}"><span class="log-num">{idx+1:03d}</span> <span class="log-text">{escaped_line}</span></div>')

        logs_container_body = "\n".join(log_html_items) if log_html_items else '<div class="log-entry log-normal"><span class="log-text">Kayıtlı oturum logu bulunamadı.</span></div>'

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Binance TR Bot - Test & Analiz Raporu</title>
    <style>
        :root {{
            --bg: #0b0e14;
            --surface: #151a24;
            --surface-hover: #1c2331;
            --border: #232d3f;
            --text: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #f59e0b;
            --success: #10b981;
            --danger: #ef4444;
            --info: #3b82f6;
            --cyan: #06b6d4;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 1150px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{ margin: 0; font-size: 24px; color: var(--accent); }}
        .badge {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
        }}
        .card-label {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .card-value {{
            font-size: 22px;
            font-weight: 700;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            margin-bottom: 28px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        th {{
            background: #1a2230;
            color: var(--text-muted);
            font-weight: 600;
        }}
        /* Log Terminal Box */
        .logs-card {{
            background: #0d111a;
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            margin-top: 24px;
        }}
        .logs-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            background: #151a24;
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
            gap: 10px;
        }}
        .logs-title {{
            font-size: 15px;
            font-weight: 600;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-group {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .btn-filter {{
            background: #1e2638;
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-filter:hover, .btn-filter.active {{
            background: var(--accent);
            color: #000;
            font-weight: bold;
        }}
        .search-box {{
            background: #0b0e14;
            border: 1px solid var(--border);
            color: var(--text);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            outline: none;
            width: 180px;
        }}
        .logs-body {{
            max-height: 480px;
            overflow-y: auto;
            padding: 12px 16px;
            font-family: "Cascadia Code", "Fira Code", Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            line-height: 1.6;
        }}
        .log-entry {{
            padding: 3px 6px;
            border-radius: 4px;
            margin-bottom: 2px;
            display: flex;
            gap: 10px;
        }}
        .log-entry:hover {{
            background: rgba(255, 255, 255, 0.04);
        }}
        .log-num {{
            color: #4b5563;
            user-select: none;
            font-size: 11px;
            min-width: 28px;
        }}
        .log-text {{
            flex: 1;
            word-break: break-all;
        }}
        .log-buy {{ color: #34d399; }}
        .log-stop {{ color: #f87171; }}
        .log-win {{ color: #10b981; font-weight: bold; }}
        .log-radar {{ color: #38bdf8; }}
        .log-calib {{ color: #fbbf24; }}
        .log-warn {{ color: #f97316; }}
        .log-normal {{ color: #d1d5db; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Binance TR Bot - Performans & Analiz Karnesi</h1>
                <p style="color: var(--text-muted); margin: 6px 0 0 0;">Oturum Zamanı: {data['generated_at']} | Parite: {cfg.get('trading', {}).get('symbol', 'USDT_TRY')}</p>
            </div>
            <div style="display: flex; gap: 8px;">
                <span class="badge">Mod: {cfg.get('trading', {}).get('mode', 'simulation').upper()}</span>
                <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: var(--info);">Süre: {cfg.get('test', {}).get('duration_minutes', 0)} dk</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-label">Net Kâr / Zarar</div>
                <div class="card-value" style="color: {pnl_color};">{pnl_prefix}{m['net_pnl']} TL ({pnl_prefix}{m['net_pnl_pct']}%)</div>
            </div>
            <div class="card">
                <div class="card-label">Kazanma Oranı (Win Rate)</div>
                <div class="card-value" style="color: var(--success);">{m['win_rate']}%</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">{m['winning_trades']} Kazanç / {m['losing_trades']} Kayıp</div>
            </div>
            <div class="card">
                <div class="card-label">Toplam İşlem Sayısı</div>
                <div class="card-value">{m['total_trades']}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Ortalama Süre: {m['avg_hold_time_seconds']}s</div>
            </div>
            <div class="card">
                <div class="card-label">Maksimum Çekilme (Drawdown)</div>
                <div class="card-value" style="color: var(--danger);">%{m['max_drawdown_pct']}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">{m['max_drawdown_amount']} TL</div>
            </div>
            <div class="card">
                <div class="card-label">Kâr Faktörü (Profit Factor)</div>
                <div class="card-value">{m['profit_factor']}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Brüt Kâr: {m['gross_profit']} TL</div>
            </div>
            <div class="card">
                <div class="card-label">Bakiye Gelişimi</div>
                <div class="card-value">{m['final_equity']} TL</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Başlangıç: {m['initial_balance']} TL</div>
            </div>
        </div>

        <h2>İşlem Detayları ({len(trades)} Kapanan İşlem)</h2>
        <table>
            <thead>
                <tr>
                    <th>Zaman</th>
                    <th>Parite</th>
                    <th>Giriş (TL)</th>
                    <th>Çıkış (TL)</th>
                    <th>Miktar</th>
                    <th>Net K/Z</th>
                    <th>Komisyon</th>
                    <th>Çıkış Nedeni</th>
                </tr>
            </thead>
            <tbody>
                {table_body}
            </tbody>
        </table>

        <h2>📌 Oturum Kapanışında Açık Kalan Pozisyonlar ({len(open_positions)} Açık)</h2>
        <table>
            <thead>
                <tr>
                    <th>Parite</th>
                    <th>Giriş Fiyatı</th>
                    <th>Son Piyasa Fiyatı</th>
                    <th>Miktar / Maliyet</th>
                    <th>Anlık K/Z (Unrealized)</th>
                    <th>Alım Gerekçesi</th>
                </tr>
            </thead>
            <tbody>
                {open_table_body}
            </tbody>
        </table>

        <!-- Terminal Logları ve Karar Geçmişi -->
        <div class="logs-card">
            <div class="logs-header">
                <div class="logs-title">
                    <span>📋 Oturum & Algoritma Karar Logları ({len(logs)} Satır)</span>
                </div>
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <div class="filter-group">
                        <button class="btn-filter active" onclick="filterLogs('all')">Tümü</button>
                        <button class="btn-filter" onclick="filterLogs('trade')">🟢 Alım/Satım</button>
                        <button class="btn-filter" onclick="filterLogs('radar')">🔍 Radar & Hız</button>
                        <button class="btn-filter" onclick="filterLogs('calib')">⏳ Kalibrasyon</button>
                        <button class="btn-filter" onclick="filterLogs('warn')">⚠️ Uyarı/Dump</button>
                    </div>
                    <input type="text" id="logSearch" class="search-box" placeholder="Loglarda ara (örn: SOL)..." onkeyup="searchLogs()">
                    <button class="btn-filter" onclick="copyLogs()">📋 Kopyala</button>
                </div>
            </div>
            <div class="logs-body" id="logsContainer">
                {logs_container_body}
            </div>
        </div>

        <!-- Birlikte Değerlendirme & Tavsiyeler -->
        <div style="margin-top: 28px; background: rgba(35, 45, 63, 0.6); border: 1px solid var(--border); border-radius: 12px; padding: 20px;">
            <h3 style="margin-top: 0; color: var(--accent); font-size: 16px;">💡 Algoritma Değerlendirmesi ve Optimizasyon Notları</h3>
            {"<p style='color: var(--text-muted); line-height: 1.6;'>Bu test oturumunda piyasa taranmış ve mikro-momentum hareketleri loglara kaydedilmiştir. Strateji sermayeyi korumak amacıyla gereksiz ve teyitsiz işlem açmamıştır.</p>" if m['total_trades'] == 0 else "<p style='color: var(--text-muted); line-height: 1.6;'>Test başarıyla tamamlandı ve kapanan işlemler kâr/zarar hedefleri doğrultusunda kaydedildi. Yukarıdaki log panelinden her bir coinin seçilme ve çıkış kararlarını adım adım analiz edebilirsiniz.</p>"}
            <ul style="color: var(--text-muted); font-size: 14px; line-height: 1.8; margin-top: 10px; padding-left: 20px;">
                <li><strong>1-Dakikalık Quant Kalibrasyonu:</strong> Bot ilk 60 saniyede piyasa mikro ivmesini analiz eder ve %+0.10 ve üzeri tutarlı yükseliş gösteren coinleri portföye dahil eder.</li>
                <li><strong>10-Saniye Ön Gözlem (Anti-Dump):</strong> Aday coinin alımı öncesinde 10 saniye beklenerek düşüş eğilimi olup olmadığı denetlenir ve sahte kırılımlar engellenir.</li>
                <li><strong>Durgunluk Tahliyesi:</strong> Pozisyon açıldıktan sonra belirlenen sürede kâra geçmeyen veya hacmi sönen coinler zararsız biçimde kapatılır.</li>
            </ul>
        </div>
    </div>

    <script>
        function filterLogs(type) {{
            document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            const entries = document.querySelectorAll('.log-entry');
            entries.forEach(e => {{
                if (type === 'all') {{
                    e.style.display = 'flex';
                }} else if (type === 'trade') {{
                    e.style.display = (e.classList.contains('log-buy') || e.classList.contains('log-stop') || e.classList.contains('log-win')) ? 'flex' : 'none';
                }} else if (type === 'radar') {{
                    e.style.display = e.classList.contains('log-radar') ? 'flex' : 'none';
                }} else if (type === 'calib') {{
                    e.style.display = e.classList.contains('log-calib') ? 'flex' : 'none';
                }} else if (type === 'warn') {{
                    e.style.display = (e.classList.contains('log-warn') || e.classList.contains('log-stop')) ? 'flex' : 'none';
                }}
            }});
        }}

        function searchLogs() {{
            const q = document.getElementById('logSearch').value.toLowerCase();
            const entries = document.querySelectorAll('.log-entry');
            entries.forEach(e => {{
                const txt = e.innerText.toLowerCase();
                e.style.display = txt.includes(q) ? 'flex' : 'none';
            }});
        }}

        function copyLogs() {{
            const entries = Array.from(document.querySelectorAll('.log-entry')).map(e => e.innerText).join('\\n');
            navigator.clipboard.writeText(entries).then(() => {{
                alert('Tüm loglar panoya kopyalandı!');
            }});
        }}
    </script>
</body>
</html>
"""

