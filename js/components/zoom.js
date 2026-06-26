"use strict";

/**
 * Zoom et deplacement (pan) du panorama : boutons +/-, molette, glisser en mode main, et « Ajuster »
 * qui recadre tout le panorama dans la fenetre. Pilote la variable CSS --zoom du cadre.
 */
(function attachZoom(namespace) {
  let editingZoom = false;          // l'utilisateur saisit une valeur exacte dans #zoomValue

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function setZoom(context, nextZoom) {
    const { elements, state } = context;
    const { min, max } = namespace.config.zoom;
    state.zoom = clamp(nextZoom, min, max);
    elements.hexWrapper.style.setProperty("--zoom", state.zoom.toString());
    if (!editingZoom) elements.zoomValue.value = `${Math.round(state.zoom * 100)}%`;
    elements.zoomIn.disabled = state.zoom >= max;
    elements.zoomOut.disabled = state.zoom <= min;
  }

  // Champ de zoom EDITABLE : clic -> on tape un nombre -> Entree (ou clic ailleurs) applique.
  function makeZoomEditable(context) {
    const { elements, state } = context;
    const zv = elements.zoomValue;
    if (!zv) return;
    zv.addEventListener("focus", () => {
      editingZoom = true;
      zv.value = String(Math.round(state.zoom * 100));   // on enleve le % pour la saisie
      zv.select();
    });
    zv.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); zv.blur(); }
      else if (event.key === "Escape") { event.preventDefault(); editingZoom = false; zv.blur(); }
    });
    zv.addEventListener("blur", () => {
      const n = parseInt((zv.value || "").replace(/[^0-9]/g, ""), 10);
      editingZoom = false;
      setZoom(context, (!isNaN(n) && n > 0 ? n / 100 : state.zoom));  // applique, ou restaure le format %
    });
  }

  // Zoom qui fait TENIR tout le panorama dans la fenetre (taille fixe oblige : "Ajuster").
  function fitZoom(context) {
    const frame = document.getElementById("hexFrame");
    const wrap = context.elements.hexWrapper;
    if (!frame || !wrap) return namespace.config.zoom.initial;
    const cs = getComputedStyle(frame);
    const fw = parseFloat(cs.getPropertyValue("--frame-w")) || frame.offsetWidth;
    const fh = parseFloat(cs.getPropertyValue("--frame-h")) || frame.offsetHeight;
    if (!fw || !fh) return namespace.config.zoom.initial;
    const availW = wrap.clientWidth - 24;
    const availH = wrap.clientHeight - 24;
    return Math.min(availW / fw, availH / fh);
  }

  // Centre le panorama dans le wrapper (il deborde a la taille fixe : on le met au milieu).
  function centerView(context) {
    const w = context.elements.hexWrapper;
    if (!w) return;
    w.scrollLeft = Math.max(0, (w.scrollWidth - w.clientWidth) / 2);
    w.scrollTop = Math.max(0, (w.scrollHeight - w.clientHeight) / 2);
  }

  // ZOOM AUTO : ajuste pour que tout le panorama tienne dans la fenetre, puis centre.
  function fitToScreen(context) {
    setZoom(context, fitZoom(context));
    centerView(context);
  }

  // Mode main : on glisse pour déplacer le panorama (au lieu des barres de défilement). Le wrapper a
  // overflow:auto, donc déplacer = ajuster scrollLeft/scrollTop.
  function bindPan(context) {
    const { elements } = context;
    const wrap = elements.hexWrapper;
    const toggle = elements.panToggle;
    if (!toggle) return;

    let panOn = false;
    let dragging = false;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;
    let moved = 0;

    function setPan(on) {
      panOn = on;
      toggle.setAttribute("aria-pressed", on ? "true" : "false");
      toggle.classList.toggle("is-active", on);
      wrap.classList.toggle("pan-mode", on);
    }
    toggle.addEventListener("click", () => setPan(!panOn));

    wrap.addEventListener("pointerdown", (event) => {
      if (!panOn || event.button !== 0) return;
      dragging = true;
      moved = 0;
      startX = event.clientX;
      startY = event.clientY;
      startLeft = wrap.scrollLeft;
      startTop = wrap.scrollTop;
      wrap.classList.add("panning");
      try { wrap.setPointerCapture(event.pointerId); } catch (e) { /* noop */ }
      event.preventDefault();
    });
    wrap.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - startX;
      const dy = event.clientY - startY;
      moved = Math.max(moved, Math.abs(dx) + Math.abs(dy));
      wrap.scrollLeft = startLeft - dx;
      wrap.scrollTop = startTop - dy;
    });
    function endDrag(event) {
      if (!dragging) return;
      dragging = false;
      wrap.classList.remove("panning");
      try { wrap.releasePointerCapture(event.pointerId); } catch (e) { /* noop */ }
    }
    wrap.addEventListener("pointerup", endDrag);
    wrap.addEventListener("pointercancel", endDrag);
    // Après un vrai glissé en mode main, on avale le clic pour ne pas ouvrir une popup secteur.
    wrap.addEventListener("click", (event) => {
      if (panOn && moved > 5) {
        event.stopPropagation();
        event.preventDefault();
        moved = 0;
      }
    }, true);
  }

  // Pincer (trackpad) ou Ctrl + molette = zoom de l'app, borné min/max. On capture l'évènement pour
  // empêcher le zoom natif du navigateur (sinon on peut grossir la page à l'infini). La molette seule
  // garde le défilement natif (déplacement à deux doigts).
  function bindWheelZoom(context) {
    const wrap = context.elements.hexWrapper;
    const { step } = namespace.config.zoom;
    wrap.addEventListener("wheel", (event) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      const dir = event.deltaY < 0 ? 1 : -1;
      setZoom(context, context.state.zoom + dir * step * 0.6);
    }, { passive: false });
  }

  function bind(context) {
    const { elements } = context;
    const { initial, step } = namespace.config.zoom;
    setZoom(context, initial);

    elements.zoomIn.addEventListener("click", () => setZoom(context, context.state.zoom + step));
    elements.zoomOut.addEventListener("click", () => setZoom(context, context.state.zoom - step));
    // "Ajuster" = fit ecran (et on recentre).
    elements.zoomReset.addEventListener("click", () => fitToScreen(context));
    makeZoomEditable(context);

    // Zoom auto : on re-ajuste quand la fenetre change de taille.
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => fitToScreen(context), 150);
    });

    bindPan(context);
    bindWheelZoom(context);
  }

  namespace.zoom = { bind, setZoom, fitZoom, centerView, fitToScreen };
})(window.CP);
