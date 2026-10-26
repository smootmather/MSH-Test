let jobId = null;
let excludedPages = new Set();
let pollTimer = null;

const el = (id) => document.getElementById(id);

function show(id, visible = true) {
  el(id).hidden = !visible;
}

el("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  show("upload-error", false);
  const file = el("pdf-input").files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("pdf", file);

  const submitBtn = e.target.querySelector("button");
  submitBtn.disabled = true;
  submitBtn.textContent = "Lade Seiten...";

  try {
    const res = await fetch("/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Unbekannter Fehler beim Hochladen.");

    jobId = data.job_id;
    excludedPages = new Set(data.pages.length ? [data.pages[0].number] : []); // Seite 1 vorab abgewaehlt (oft Titelblatt)
    renderPageGrid(data.pages);
    show("step-pages", true);
    el("step-pages").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    el("upload-error").textContent = err.message;
    show("upload-error", true);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Seiten laden";
  }
});

function renderPageGrid(pages) {
  const grid = el("page-grid");
  grid.innerHTML = "";
  for (const page of pages) {
    const tile = document.createElement("div");
    tile.className = "page-tile";
    tile.dataset.page = page.number;
    tile.innerHTML = `<img src="${page.thumb_url}" alt="Seite ${page.number}">
                       <div class="num">Seite ${page.number}</div>`;
    tile.addEventListener("click", () => togglePage(page.number, tile));
    grid.appendChild(tile);
    updateTileClass(tile, page.number);
  }
}

function togglePage(number, tile) {
  if (excludedPages.has(number)) {
    excludedPages.delete(number);
  } else {
    excludedPages.add(number);
  }
  updateTileClass(tile, number);
}

function updateTileClass(tile, number) {
  tile.classList.toggle("excluded", excludedPages.has(number));
  tile.classList.toggle("included", !excludedPages.has(number));
}

el("convert-btn").addEventListener("click", async () => {
  const allTiles = [...document.querySelectorAll(".page-tile")];
  const included = allTiles
    .map((t) => parseInt(t.dataset.page, 10))
    .filter((n) => !excludedPages.has(n));

  if (included.length === 0) {
    alert("Bitte mindestens eine Seite auswaehlen.");
    return;
  }

  show("step-progress", true);
  show("convert-error", false);
  el("log-tail").textContent = "";
  el("step-progress").scrollIntoView({ behavior: "smooth" });

  const res = await fetch(`/convert/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pages: included }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("convert-error").textContent = data.error || "Fehler beim Start der Umwandlung.";
    show("convert-error", true);
    return;
  }

  pollTimer = setInterval(pollStatus, 1500);
});

async function pollStatus() {
  const res = await fetch(`/status/${jobId}`);
  const data = await res.json();

  el("log-tail").textContent = data.log_tail.join("\n");
  el("log-tail").scrollTop = el("log-tail").scrollHeight;

  if (data.status === "error") {
    clearInterval(pollTimer);
    el("convert-error").textContent = data.error;
    show("convert-error", true);
  } else if (data.status === "awaiting_instruments") {
    clearInterval(pollTimer);
    lastWarnings = data.warnings || [];
    await showInstrumentStep(data.parts || []);
  }
}

let lastWarnings = [];
let instrumentOptions = [];

async function showInstrumentStep(parts) {
  if (instrumentOptions.length === 0) {
    const res = await fetch("/instrument-options");
    instrumentOptions = await res.json();
  }

  const table = el("instrument-table");
  table.innerHTML = "";
  for (const part of parts) {
    const num = document.createElement("div");
    num.className = "row-num";
    num.textContent = part.index;

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = "";
    nameInput.placeholder = `z.B. "1. B-Klarinette"`;
    nameInput.dataset.index = part.index;
    nameInput.className = "part-name-input";

    const select = document.createElement("select");
    select.dataset.index = part.index;
    select.className = "part-transposition-select";
    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "— nicht zuweisen —";
    select.appendChild(noneOpt);
    for (const opt of instrumentOptions) {
      const o = document.createElement("option");
      o.value = opt.key;
      o.textContent = opt.label;
      select.appendChild(o);
    }
    select.addEventListener("change", () => {
      if (select.value && !nameInput.value) {
        const label = instrumentOptions.find((o) => o.key === select.value);
        nameInput.value = label ? label.label : "";
      }
    });

    table.appendChild(num);
    table.appendChild(nameInput);
    table.appendChild(select);
  }

  show("step-instruments", true);
  el("step-instruments").scrollIntoView({ behavior: "smooth" });
}

el("assign-btn").addEventListener("click", async () => {
  show("assign-error", false);
  const rows = [...document.querySelectorAll(".part-transposition-select")];
  const assignments = rows
    .map((select) => {
      const index = select.dataset.index;
      const nameInput = document.querySelector(`.part-name-input[data-index="${index}"]`);
      return {
        index: parseInt(index, 10),
        transposition_key: select.value || "concert_pitch",
        name: nameInput.value,
      };
    })
    .filter((a) => a.name && a.name.trim().length > 0);

  await submitAssignments(assignments);
});

el("skip-instruments-btn").addEventListener("click", async () => {
  await submitAssignments([]);
});

async function submitAssignments(assignments) {
  const res = await fetch(`/assign/${jobId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assignments }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("assign-error").textContent = data.error || "Fehler bei der Instrumentenzuweisung.";
    show("assign-error", true);
    return;
  }
  finishUp();
}

function finishUp() {
  show("step-instruments", false);
  el("download-link").href = `/download/${jobId}`;
  if (lastWarnings.length) {
    el("warnings-list").innerHTML = lastWarnings
      .slice(0, 20)
      .map((w) => `<li>${escapeHtml(w)}</li>`)
      .join("");
    show("warnings-box", true);
  } else {
    show("warnings-box", false);
  }
  show("step-done", true);
  el("step-done").scrollIntoView({ behavior: "smooth" });
}

el("restart-btn").addEventListener("click", () => {
  location.reload();
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
