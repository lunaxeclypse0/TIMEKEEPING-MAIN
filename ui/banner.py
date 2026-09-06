from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components


def render_top_banner(logo_b64: str | None, logo_mime: str = "image/png") -> None:
    if logo_b64:
        logo_html = (
            f'<img src="data:{logo_mime};base64,{logo_b64}" '
            f'alt="GoClinic Logo" class="hero-logo">'
        )
    else:
        logo_html = '<div class="hero-fallback">🏥</div>'

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  html, body {{
    width: 100%;
    background: transparent;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}

  body {{
    padding: 0;
  }}

  .wrap {{
    width: 100%;
    padding: 0;
  }}

  .hero {{
    width: 100%;
    min-height: 160px;
    background: linear-gradient(120deg, #0c1f4a 0%, #1740a0 55%, #2563eb 100%);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 24px;
    gap: 16px;
    box-shadow: 0 10px 36px rgba(21, 60, 160, 0.32);
    position: relative;
    overflow: hidden;
  }}

  .hero::before {{
    content: '';
    position: absolute;
    top: -60px;
    right: -60px;
    width: 260px;
    height: 260px;
    border-radius: 50%;
    background: rgba(255,255,255,0.04);
    pointer-events: none;
  }}

  .hero::after {{
    content: '';
    position: absolute;
    bottom: -80px;
    left: 160px;
    width: 220px;
    height: 220px;
    border-radius: 50%;
    background: rgba(255,255,255,0.03);
    pointer-events: none;
  }}

  .hero-left,
  .hero-center,
  .hero-right {{
    position: relative;
    z-index: 1;
  }}

  .hero-left {{
    width: 220px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-shrink: 0;
  }}

  .hero-logo {{
    max-width: 210px;
    max-height: 110px;
    width: 100%;
    height: auto;
    object-fit: contain;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,0.22));
    display: block;
  }}

  .hero-fallback {{
    width: 84px;
    height: 84px;
    border-radius: 18px;
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.2rem;
  }}

  .hero-center {{
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
  }}

  .hero-title {{
    font-size: clamp(1.55rem, 2vw + 0.6rem, 2.2rem);
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -0.8px;
    line-height: 1.02;
    text-shadow: 0 2px 12px rgba(0,0,0,0.18);
    word-break: break-word;
  }}

  .hero-title span {{
    color: #93c5fd;
  }}

  .hero-tagline {{
    font-size: clamp(0.70rem, 0.45vw + 0.58rem, 0.78rem);
    color: rgba(255,255,255,0.68);
    margin-top: 7px;
    font-weight: 500;
    letter-spacing: 0.35px;
    line-height: 1.35;
  }}

  .hero-right {{
    width: 210px;
    display: flex;
    justify-content: flex-end;
    flex-shrink: 0;
  }}

  .clock-card {{
    width: 196px;
    min-height: 110px;
    border-radius: 18px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.20);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.14), 0 4px 16px rgba(0,0,0,0.14);
    padding: 10px 12px;
  }}

  .clock-date {{
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1.8px;
    color: rgba(255,255,255,0.60);
    text-transform: uppercase;
    text-align: center;
  }}

  .clock-time {{
    font-size: clamp(1.8rem, 1.5vw + 1rem, 2.3rem);
    font-weight: 900;
    color: #ffffff;
    line-height: 1;
    letter-spacing: 1.5px;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum';
    text-align: center;
  }}

  .clock-label {{
    font-size: 0.60rem;
    font-weight: 800;
    letter-spacing: 3px;
    color: rgba(255,255,255,0.48);
    text-transform: uppercase;
    text-align: center;
  }}

  /* Tablet */
  @media (max-width: 900px) {{
    .hero {{
      padding: 16px 18px;
      gap: 14px;
      border-radius: 18px;
    }}

    .hero-left {{
      width: 170px;
    }}

    .hero-logo {{
      max-width: 160px;
      max-height: 84px;
    }}

    .hero-right {{
      width: 180px;
    }}

    .clock-card {{
      width: 170px;
      min-height: 100px;
      border-radius: 16px;
    }}

    .clock-time {{
      letter-spacing: 1px;
    }}
  }}

  /* Mobile */
  @media (max-width: 680px) {{
    body {{
      padding: 0;
    }}

    .hero {{
      min-height: auto;
      flex-direction: column;
      align-items: stretch;
      justify-content: center;
      text-align: center;
      padding: 18px 16px;
      gap: 14px;
      border-radius: 16px;
    }}

    .hero::before {{
      width: 180px;
      height: 180px;
      top: -70px;
      right: -60px;
    }}

    .hero::after {{
      width: 160px;
      height: 160px;
      bottom: -80px;
      left: -30px;
    }}

    .hero-left,
    .hero-center,
    .hero-right {{
      width: 100%;
      justify-content: center;
      align-items: center;
    }}

    .hero-left {{
      display: flex;
    }}

    .hero-logo {{
      max-width: 170px;
      max-height: 78px;
      margin: 0 auto;
    }}

    .hero-fallback {{
      width: 72px;
      height: 72px;
      font-size: 2rem;
      border-radius: 16px;
      margin: 0 auto;
    }}

    .hero-title {{
      font-size: clamp(1.35rem, 4.6vw, 1.9rem);
      line-height: 1.08;
    }}

    .hero-tagline {{
      font-size: 0.74rem;
      margin-top: 6px;
      max-width: 34ch;
    }}

    .hero-right {{
      display: flex;
    }}

    .clock-card {{
      width: 100%;
      max-width: 240px;
      min-height: 96px;
      margin: 0 auto;
      border-radius: 16px;
    }}

    .clock-date {{
      font-size: 0.64rem;
      letter-spacing: 1.4px;
    }}

    .clock-time {{
      font-size: clamp(1.55rem, 6vw, 2rem);
    }}

    .clock-label {{
      letter-spacing: 2.2px;
    }}
  }}

  /* Extra small phones */
  @media (max-width: 420px) {{
    .hero {{
      padding: 16px 14px;
      gap: 12px;
      border-radius: 14px;
    }}

    .hero-logo {{
      max-width: 150px;
      max-height: 70px;
    }}

    .hero-title {{
      font-size: 1.28rem;
    }}

    .hero-tagline {{
      font-size: 0.70rem;
    }}

    .clock-card {{
      min-height: 90px;
      padding: 10px;
    }}

    .clock-time {{
      font-size: 1.45rem;
    }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="hero-left">{logo_html}</div>

      <div class="hero-center">
        <h1 class="hero-title">Timekeeping <span>System</span></h1>
        <div class="hero-tagline">Automated Attendance Processing &amp; DTR Generator</div>
      </div>

      <div class="hero-right">
        <div class="clock-card">
          <div class="clock-date" id="live-date">Loading...</div>
          <div class="clock-time" id="live-time">00:00:00</div>
          <div class="clock-label">Live Clock</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    function pad(n) {{
      return String(n).padStart(2, '0');
    }}

    function tick() {{
      const now = new Date();
      const timeEl = document.getElementById('live-time');
      const dateEl = document.getElementById('live-date');

      if (!timeEl || !dateEl) return;

      timeEl.textContent =
        pad(now.getHours()) + ':' +
        pad(now.getMinutes()) + ':' +
        pad(now.getSeconds());

      dateEl.textContent =
        DAYS[now.getDay()] + ', ' +
        MONTHS[now.getMonth()] + ' ' +
        now.getDate();
    }}

    tick();
    setInterval(tick, 1000);
  </script>
</body>
</html>"""

    if hasattr(st, "iframe"):
        st.iframe(html, height=240)
    else:
        # Backward compatibility for Streamlit releases before st.iframe.
        components.html(html, height=240, scrolling=False)
