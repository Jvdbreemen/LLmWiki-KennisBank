// Timeline lens (27.7): weekly activity buckets, event-time vs capture-time.
import type { DataClient, Timeline } from "../data-client";
import { clear, el, withLoader } from "../dom";

export function renderTimelineLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Timeline>(host, "timeline laden…", () => client.timeline(), (data) => {
    if (data.status === "empty" || data.buckets.length === 0) {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen activity-data"]));
      return;
    }
    const max = Math.max(
      1,
      ...data.buckets.map((b) => Math.max(b.event_count, b.capture_count)),
    );
    const chart = el("div", { class: "timeline-chart" });
    for (const b of data.buckets) {
      const col = el("div", { class: "tl-col", title: `${b.start.slice(0, 10)} · events ${b.event_count} · captures ${b.capture_count}` });
      const ev = el("div", { class: "tl-bar tl-event" });
      ev.style.height = `${(b.event_count / max) * 100}%`;
      const cap = el("div", { class: "tl-bar tl-capture" });
      cap.style.height = `${(b.capture_count / max) * 100}%`;
      col.appendChild(ev);
      col.appendChild(cap);
      col.appendChild(el("div", { class: "tl-label" }, [b.start.slice(5, 10)]));
      chart.appendChild(col);
    }
    clear(host);
    host.appendChild(el("div", { class: "lens-pad" }, [
      el("h2", {}, ["Activity timeline (per week)"]),
      el("div", { class: "legend" }, [
        el("span", { class: "swatch tl-event" }, []), "event-tijd  ",
        el("span", { class: "swatch tl-capture" }, []), "capture-tijd",
      ]),
      chart,
    ]));
  });
}
