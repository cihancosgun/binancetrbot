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
        equity_curve: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(self.reports_dir, f"test_run_{timestamp_str}.json")
        html_path = os.path.join(self.reports_dir, f"test_run_{timestamp_str}.html")

        full_data = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": config_data,
            "metrics": metrics,
            "trades": closed_trades,
            "equity_curve": equity_curve,
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

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Binance TR Bot - Test Performans Raporu</title>
    <style>
        :root {{
            --bg: #0b0e14;
            --surface: #151a24;
            --border: #232d3f;
            --text: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #f59e0b;
            --success: #10b981;
            --danger: #ef4444;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 1100px;
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Binance TR Bot - Performans Test Karnesi</h1>
                <p style="color: var(--text-muted); margin: 6px 0 0 0;">Oturum Zamanı: {data['generated_at']} | Parite: {cfg.get('trading', {}).get('symbol', 'USDT_TRY')}</p>
            </div>
            <div>
                <span class="badge">Mod: {cfg.get('trading', {}).get('mode', 'simulation').upper()}</span>
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

        <h2>İşlem Detayları</h2>
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

        <!-- Birlikte Değerlendirme & Tavsiyeler -->
        <div style="margin-top: 28px; background: rgba(35, 45, 63, 0.6); border: 1px solid var(--border); border-radius: 12px; padding: 20px;">
            <h3 style="margin-top: 0; color: var(--accent); font-size: 16px;">💡 Algoritma Değerlendirmesi ve Optimizasyon Notları</h3>
            {"<p style='color: var(--text-muted); line-height: 1.6;'>Bu 15-20 dakikalık test oturumunda piyasa koşulları belirlenen alış stratejisi kriterlerini (aşırı satım / dip kırılımı) tetikleyecek kadar sert düşüş veya dalgalanma yaşamadı. Strateji sermayeyi korumak amacıyla gereksiz işlem açmadı.</p>" if m['total_trades'] == 0 else "<p style='color: var(--text-muted); line-height: 1.6;'>Test başarıyla tamamlandı ve kapanan işlemler kâr/zarar hedefleri doğrultusunda kaydedildi.</p>"}
            <ul style="color: var(--text-muted); font-size: 14px; line-height: 1.8; margin-top: 10px; padding-left: 20px;">
                <li><strong>Hızlı Test İçin:</strong> Web panelinde 'Strateji' olarak <code>Hızlı Test Scalper</code> seçilerek 15 dakikalık sürede sık işlem fırsatları yakalanabilir.</li>
                <li><strong>Volatil Parite Tercihi:</strong> <code>USDT_TRY</code> sabit kur olduğundan, kısa sürede hareket görmek için <code>SOL_TRY</code>, <code>BTC_TRY</code> veya <code>PEPE_TRY</code> gibi dalgalı pariteler kullanılabilir.</li>
                <li><strong>Anında Test:</strong> Web panelindeki <code>⚡ Anında Test Alımı Yap</code> butonuna basılarak doğrudan canlı tahtada pozisyon açılabilir ve Kâr Al / Stop Loss anlık takip edilebilir.</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
