"use strict";

/**
 * Fiche detaillee d'une solution (modale) : logo, fonction NIST, description, site/contact, categories
 * et sous-categories NIST. Ouverte au clic sur un logo, fermee par la croix, l'exterieur ou Echap.
 */
(function attachModal(namespace) {
  const { assetPath, initials, tagLightLogo } = namespace.utils;

  function setLogo(solution, elements) {
    elements.modalLogo.replaceChildren();
    elements.modalLogo.classList.remove("logo-on-dark");
    if (solution.logo_path) {
      const image = document.createElement("img");
      image.src = assetPath(solution.logo_path);
      image.alt = "";
      image.addEventListener(
        "error",
        () => {
          image.remove();
          elements.modalLogo.textContent = initials(solution.solution_name);
        },
        { once: true },
      );
      elements.modalLogo.appendChild(image);
      tagLightLogo(image, elements.modalLogo, solution.id); // fond foncé auto si le logo est blanc
    } else {
      elements.modalLogo.textContent = initials(solution.solution_name);
    }
  }

  function cell(label, value) {
    const node = document.createElement("div");
    node.className = "modal-cell";
    const l = document.createElement("span");
    l.className = "modal-cell-label";
    l.textContent = label;
    const v = document.createElement("span");
    v.className = "modal-cell-value";
    if (value instanceof Node) {
      v.appendChild(value);
    } else {
      v.textContent = value || "Non renseigné";
    }
    node.append(l, v);
    return node;
  }

  // Construit un href sur : on n'autorise que http(s) (ou le prefixe fixe mailto:/tel:). Une valeur
  // de donnee comme "javascript:..." ou "data:..." (saisie via formulaire) est rejetee pour eviter
  // l'execution de script au clic. Sans schema, on prefixe https://.
  function safeHref(url, prefix) {
    if (prefix) return `${prefix}${url}`;
    if (/^https?:\/\//i.test(url)) return url;
    if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return null; // tout autre schema (javascript:, data:, vbscript:...)
    return `https://${url.replace(/^\/+/, "")}`;
  }

  function link(url, prefix = "", cls = "") {
    if (!url) return document.createTextNode("Non renseigné");
    const href = safeHref(url, prefix);
    if (!href) return document.createTextNode(url); // schema non autorise : texte brut, pas de lien
    const a = document.createElement("a");
    a.href = href;
    a.target = prefix ? "" : "_blank";
    a.rel = prefix ? "" : "noreferrer noopener";
    a.textContent = url;
    if (cls) a.className = cls;
    return a;
  }

  function tagList(values, catalog) {
    const wrap = document.createElement("div");
    wrap.className = "modal-tags";
    if (!values.length) {
      const t = document.createElement("span");
      t.className = "modal-tag empty";
      t.textContent = "Non renseigné";
      wrap.appendChild(t);
      return wrap;
    }
    values.forEach((code) => {
      const t = document.createElement("span");
      t.className = "modal-tag";
      const entry = catalog && catalog[code];
      const label =
        typeof entry === "string" ? entry : (entry && entry.label) || "";
      t.textContent = label ? `${label} (${code})` : code;
      t.title = label ? `${code} ${label}` : code;
      wrap.appendChild(t);
    });
    return wrap;
  }

  function section(title, node) {
    const wrap = document.createElement("div");
    wrap.className = "modal-section";
    const h = document.createElement("h3");
    h.textContent = title;
    wrap.append(h, node);
    return wrap;
  }

  function open(solutionId, context) {
    const { elements, solutionsById, state } = context;
    const solution = solutionsById.get(solutionId);
    if (!solution) return;

    state.modalSolutionId = solutionId;
    // évite la redondance entreprise / nom de solution (souvent identiques)
    const company =
      solution.company_name && solution.company_name !== solution.solution_name
        ? solution.company_name
        : "";
    elements.modalCompany.textContent = company;
    elements.modalCompany.hidden = !company;
    elements.modalTitle.textContent = solution.solution_name;
    elements.modalFunction.textContent = solution.nist.level1;

    const modalEl = elements.modal.querySelector(".modal");
    modalEl.dataset.sector = solution.nist.level1;
    elements.modalFunction.parentElement.dataset.sector = solution.nist.level1;

    setLogo(solution, elements);

    const description = document.createElement("p");
    description.className = "modal-description";
    description.textContent =
      solution.description || "Description non renseignée.";

    const grid = document.createElement("div");
    grid.className = "modal-grid";
    const contactNode = solution.email_contact
      ? link(solution.email_contact, "mailto:", "lnk-plain")
      : solution.contact_url
        ? link(solution.contact_url, "", "lnk-plain")
        : document.createTextNode("Non renseigné");
    grid.append(
      cell("Site web", link(solution.website, "", "lnk-web")),
      cell("Contact", contactNode),
    );

    const data = window.CYBERPANORAMA_DATA || {};
    elements.modalBody.replaceChildren(
      description,
      grid,
      section(
        "Catégories NIST niveau 2",
        tagList(solution.nist.level2, data.level2_catalog),
      ),
      section(
        "Sous-catégories NIST niveau 3",
        tagList(solution.nist.level3, data.level3_catalog),
      ),
    );

    elements.modal.hidden = false;
    elements.modalClose.focus();
  }

  function close(context) {
    context.elements.modal.hidden = true;
    context.state.modalSolutionId = null;
  }

  function bind(context) {
    const { elements } = context;
    elements.modalClose.addEventListener("click", () => close(context));
    elements.modal.addEventListener("click", (event) => {
      if (event.target === elements.modal) close(context);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !elements.modal.hidden) close(context);
    });
  }

  namespace.modal = { bind, close, open };
})(window.CP);
