/* Shared burger menu for every Evorium page: Dashboard, Map, 3D, Timeline and Guide.
   Include with <script src="/static/nav.js" defer></script>. It adds a ☰ button to the page's <header>
   (top right, beside any existing button) and a small panel listing the pages, with the current one highlighted. */
(() => {
  'use strict';
  const PAGES = [
    {label: 'Dashboard', href: '/game#dashboard', id: 'dashboard'},
    {label: 'Map', href: '/game#map', id: 'map'},
    {label: '3D', href: '/world3d', id: '3d'},
    {label: 'Timeline', href: '/timeline-page', id: 'timeline'},
    {label: 'Guide', href: '/guide', id: 'guide'},
  ];

  function currentPage(path = location.pathname, hash = location.hash) {
    if (path.startsWith('/world3d')) return '3d';
    if (path.startsWith('/timeline')) return 'timeline';
    if (path.startsWith('/guide')) return 'guide';
    return hash === '#map' ? 'map' : 'dashboard';
  }

  const css = `
  .evo-burger{display:inline-flex;flex-direction:column;justify-content:center;gap:4px;width:40px;height:36px;
    padding:0 10px;margin-left:auto;background:#1e1e1e;border:1px solid #444;border-radius:7px;cursor:pointer;
    pointer-events:auto;flex:none}
  .evo-burger span{display:block;height:2px;background:#e8e8e8;border-radius:2px}
  .evo-burger:hover{background:#2a2a2a}
  .evo-burger:focus-visible,.evo-nav a:focus-visible{outline:2px solid #d4a24c;outline-offset:2px}
  .evo-nav{position:fixed;z-index:50;top:62px;right:max(16px,env(safe-area-inset-right));min-width:200px;
    background:#1b1b1bf7;border:1px solid #444;border-radius:12px;box-shadow:0 14px 50px #000a;padding:8px;
    font:16px system-ui,sans-serif}
  .evo-nav[hidden]{display:none}
  .evo-nav a{display:block;padding:12px 16px;border-radius:8px;color:#e8e8e8;text-decoration:none}
  .evo-nav a:hover{background:#2a2a2a}
  .evo-nav a[aria-current="page"]{background:#d4a24c;color:#141414;font-weight:600}
  @media (max-width:600px){.evo-nav{left:16px;right:16px;top:70px}.evo-nav a{padding:16px;font-size:18px}}`;

  function build() {
    if (document.querySelector('.evo-burger')) return;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'evo-burger';
    button.setAttribute('aria-label', 'Menu');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', 'evo-nav');
    button.innerHTML = '<span></span><span></span><span></span>';

    const nav = document.createElement('nav');
    nav.id = 'evo-nav';
    nav.className = 'evo-nav';
    nav.setAttribute('aria-label', 'Evorium pages');
    nav.hidden = true;
    const here = currentPage();
    for (const page of PAGES) {
      const link = document.createElement('a');
      link.href = page.href;
      link.textContent = page.label;
      if (page.id === here) link.setAttribute('aria-current', 'page');
      nav.appendChild(link);
    }

    const header = document.querySelector('header');
    if (header) {
      // If something is already pushed to the right (the 3D settings gear, the dashboard's version/Restart), sit beside it.
      if (header.querySelector('#settings-button, #version, #restart')) button.style.marginLeft = '8px';
      header.appendChild(button);
    } else {
      Object.assign(button.style, {position: 'fixed', top: '14px', right: '16px', zIndex: '50'});
      document.body.appendChild(button);
    }
    document.body.appendChild(nav);

    const open = () => {
      nav.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      if (document.pointerLockElement) document.exitPointerLock();   // 3D: give the mouse back
      nav.querySelector('a')?.focus();
    };
    const close = (focusButton = false) => {
      nav.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      if (focusButton) button.focus();
    };
    button.addEventListener('click', event => {
      event.stopPropagation();
      nav.hidden ? open() : close();
    });
    nav.addEventListener('click', event => {
      if (event.target.closest('a')) close();
    });
    document.addEventListener('click', event => {
      if (!nav.hidden && !nav.contains(event.target) && event.target !== button) close();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !nav.hidden) close(true);
    });
    // The dashboard switches between Dashboard and Map without reloading: keep the highlight right.
    window.addEventListener('hashchange', () => {
      const now = currentPage();
      for (const link of nav.querySelectorAll('a')) {
        const id = PAGES.find(page => page.href === link.getAttribute('href')).id;
        if (id === now) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
      }
    });
  }

  if (typeof module !== 'undefined') module.exports = {currentPage, PAGES};   // node tests
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
    else build();
  }
})();
