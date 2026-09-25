"use strict";

const PRIORITIES = [
  ["high", "High"], ["medium", "Medium"], ["low", "Low"],
  ["alignment_only", "Alignment-only"],
];
const state = { payload: null, priority: "high", index: 0, zoom: 1 };
const el = (id) => document.getElementById(id);

function node(tag, className = "", content = "") {
  const item = document.createElement(tag);
  if (className) item.className = className;
  item.textContent = content;
  return item;
}

function words(value) { return value.match(/[^\s]+/gu) || []; }

// Highlight differences against the alignment anchor, which is not a
// preferred reading. Do not change or normalize the displayed OCR text.
function differenceMasks(leftText, rightText) {
  const left = words(leftText);
  const right = words(rightText);
  if (left.length * right.length > 40000) return null;
  const table = Array.from(
    { length: left.length + 1 }, () => new Uint16Array(right.length + 1)
  );
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      table[i][j] = left[i] === right[j]
        ? 1 + table[i + 1][j + 1]
        : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const changedLeft = Array(left.length).fill(true);
  const changedRight = Array(right.length).fill(true);
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      changedLeft[i] = false;
      changedRight[j] = false;
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }
  return { changedLeft, changedRight };
}

function renderText(value, changed) {
  const pre = node("pre", "candidate-text");
  if (!value) {
    pre.classList.add("no-reading");
    pre.textContent = "[No confidently aligned reading]";
    return pre;
  }
  let wordIndex = 0;
  for (const part of value.match(/\s+|[^\s]+/gu) || []) {
    if (/^\s+$/u.test(part)) {
      pre.append(document.createTextNode(part));
    } else {
      pre.append(changed?.[wordIndex]
        ? node("mark", "", part) : document.createTextNode(part));
      wordIndex++;
    }
  }
  return pre;
}

function queue() {
  return state.payload.packet.segments.filter(
    (segment) => segment.review_priority === state.priority
  );
}

function renderTabs() {
  const tabs = el("queue-tabs");
  tabs.replaceChildren();
  for (const [key, label] of PRIORITIES) {
    const count = state.payload.packet.priority_counts[key] || 0;
    const button = node("button", "", `${label} ${count}`);
    button.type = "button";
    button.setAttribute("aria-pressed", String(key === state.priority));
    button.addEventListener("click", () => {
      state.priority = key;
      state.index = 0;
      renderReview();
    });
    tabs.append(button);
  }
}

function renderList(items) {
  const list = el("segment-list");
  list.replaceChildren();
  for (const [index, segment] of items.entries()) {
    const button = node("button", "", segment.id);
    button.type = "button";
    button.setAttribute("aria-current", String(index === state.index));
    const lines = segment.anchor_line_numbers?.join(", ") || "not aligned";
    button.append(node("small", "", `Anchor OCR line ${lines}`));
    button.addEventListener("click", () => {
      state.index = index;
      renderReview();
    });
    list.append(button);
  }
  list.querySelector('[aria-current="true"]')?.scrollIntoView({ block: "nearest" });
}

function renderCandidates(segment) {
  const packet = state.payload.packet;
  const container = el("candidate-readings");
  container.replaceChildren();
  const anchorText = segment.readings[packet.alignment_anchor]?.text || "";
  const masks = {};
  const anchorChanged = Array(words(anchorText).length).fill(false);
  for (const name of packet.available_candidates) {
    if (name === packet.alignment_anchor) continue;
    const reading = segment.readings[name];
    if (reading?.alignment !== "aligned" || !reading.text) continue;
    const pair = differenceMasks(anchorText, reading.text);
    if (!pair) continue;
    masks[name] = pair.changedRight;
    pair.changedLeft.forEach((changed, index) => { anchorChanged[index] ||= changed; });
  }
  for (const name of packet.available_candidates) {
    const reading = segment.readings[name];
    const card = node("article", "candidate-card");
    card.append(node("h3", "", name));
    const meta = node("div", "candidate-meta");
    const alignment = reading?.alignment || "unaligned";
    meta.append(node("span", `alignment-badge alignment-${alignment}`, alignment));
    meta.append(node("span", "", `OCR lines: ${reading?.line_numbers?.join(", ") || "—"}`));
    if (reading?.similarity !== null && reading?.similarity !== undefined) {
      meta.append(node("span", "", `Similarity: ${Math.round(reading.similarity * 100)}%`));
    }
    if (reading?.anchor_coverage !== null && reading?.anchor_coverage !== undefined) {
      meta.append(node("span", "", `Coverage: ${Math.round(reading.anchor_coverage * 100)}%`));
    }
    card.append(meta);
    card.append(renderText(reading?.text || "",
      name === packet.alignment_anchor ? anchorChanged : masks[name]));
    container.append(card);
  }
  if (segment.flags?.length) {
    const details = node("details", "flags");
    details.append(node("summary", "", `${segment.flags.length} inspection flag(s)`));
    const list = node("ul");
    for (const flag of segment.flags) {
      list.append(node("li", "", `${flag.category}: ${(flag.examples || []).join("; ")}`));
    }
    details.append(list);
    container.append(details);
  }
}

function renderReview() {
  const items = queue();
  renderTabs();
  renderList(items);
  el("queue-position").textContent = items.length
    ? `${state.index + 1} / ${items.length}` : "No segments";
  el("previous-segment").disabled = state.index <= 0;
  el("next-segment").disabled = state.index >= items.length - 1;
  const heading = el("segment-heading");
  heading.replaceChildren();
  el("segment-reasons").textContent = "";
  el("candidate-readings").replaceChildren();
  if (!items.length) {
    heading.append(node("p", "", "No segments in this queue."));
    return;
  }
  const segment = items[state.index];
  const title = node("div", "segment-title");
  title.append(node("h3", "",
    `${segment.id} · OCR anchor line(s) ${segment.anchor_line_numbers.join(", ")}`));
  title.append(node("span", `priority-badge priority-${state.priority}`,
    state.priority.replace("_", " ")));
  heading.append(title);
  el("segment-reasons").textContent =
    `Agreement: ${segment.agreement}. Inspection reason(s): ${(segment.priority_reasons || []).join(", ") || "none"}. Highlighting compares tokens with the alignment anchor, not with a correct reading.`;
  renderCandidates(segment);
}

function setZoom(value) {
  state.zoom = Math.max(0.5, Math.min(3, value));
  el("scan-image").style.width = `${Math.round(state.zoom * 100)}%`;
}

function renderUnaligned(blocks) {
  el("unaligned-heading").textContent = `Unaligned OCR blocks (${blocks.length})`;
  const list = el("unaligned-list");
  list.replaceChildren();
  if (!blocks.length) {
    list.append(node("p", "", "None."));
    return;
  }
  for (const block of blocks) {
    const card = node("article", "candidate-card");
    card.append(node("h3", "", block.candidate));
    card.append(node("div", "candidate-meta",
      `OCR lines: ${block.line_numbers.join(", ")} · not assigned to a segment`));
    card.append(renderText(block.text));
    list.append(card);
  }
}

function initialize(payload) {
  state.payload = payload;
  const packet = payload.packet;
  const status = payload.review_status;
  el("page-context").textContent =
    `PDF ${packet.pdf_page} · printed ${packet.printed_label || "unrecorded"} · ` +
    `${packet.selected_feature || "feature unrecorded"} · ` +
    `${packet.available_candidates.length} OCR candidates available` +
    (packet.unavailable_candidates.length ? ` · ${packet.unavailable_candidates.length} missing` : "") +
    (packet.empty_candidates.length ? ` · ${packet.empty_candidates.length} empty` : "");
  el("candidate-availability").textContent = [
    `Available: ${packet.available_candidates.join(", ") || "none"}`,
    `Missing: ${packet.unavailable_candidates.join(", ") || "none"}`,
    `Empty/unusable: ${packet.empty_candidates.join(", ") || "none"}`,
  ].join(" · ");
  const badge = el("review-status");
  badge.textContent = status.replace("_", " ");
  badge.className = `status ${status === "in_review" ? "in-review" : status}`;
  const transcriptionLabel = el("transcription-label");
  transcriptionLabel.textContent = status === "verified"
    ? "Verified transcription" : "Working text · not verified";
  transcriptionLabel.className =
    `transcription-label ${status === "in_review" ? "in-review" : status}`;
  el("transcription-text").textContent =
    payload.transcription || "[No human transcription text recorded for this page]";
  if (payload.packet_status_outdated) {
    const warning = el("error");
    warning.textContent =
      "The saved packet has an older review status. The header uses the current review log; regenerate the packet before relying on its metadata.";
    warning.hidden = false;
  }
  if (payload.image_available) {
    const image = el("scan-image");
    image.src = payload.image_url;
    image.hidden = false;
    image.addEventListener("error", () => {
      image.hidden = true;
      el("image-unavailable").hidden = false;
    });
  } else {
    el("image-unavailable").hidden = false;
  }
  state.priority = PRIORITIES.find(([key]) => packet.priority_counts[key] > 0)?.[0] || "high";
  renderUnaligned(packet.unaligned_candidate_lines || []);
  el("workspace").hidden = false;
  renderReview();
}

el("previous-segment").addEventListener("click", () => {
  if (state.index > 0) { state.index--; renderReview(); }
});
el("next-segment").addEventListener("click", () => {
  if (state.index < queue().length - 1) { state.index++; renderReview(); }
});
el("zoom-out").addEventListener("click", () => setZoom(state.zoom / 1.25));
el("zoom-reset").addEventListener("click", () => setZoom(1));
el("zoom-in").addEventListener("click", () => setZoom(state.zoom * 1.25));

fetch("/api/page", { cache: "no-store" })
  .then((response) => {
    if (!response.ok) throw new Error(`Local data request failed (${response.status})`);
    return response.json();
  })
  .then(initialize)
  .catch((error) => {
    el("error").textContent = error.message;
    el("error").hidden = false;
  });
