# -*- coding: utf-8 -*-
import os
import json
import time
import re
from typing import List, Dict, Tuple, Optional

def parse_srt_subtitles(content: str) -> list:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", content.strip()) if b.strip()]
    stamp_re = re.compile(
        r"(\d{1,3}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,3}:\d{2}:\d{2}[,\.]\d{3})"
    )

    def parse_ms(stamp_str):
        stamp_str = stamp_str.replace(",", ".")
        h, m, s = stamp_str.split(":")
        return int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)

    subs = []
    idx = 1
    for block in blocks:
        lines = block.splitlines()
        stamp_line_idx = -1
        for i, l in enumerate(lines):
            if stamp_re.search(l):
                stamp_line_idx = i
                break
        if stamp_line_idx == -1:
            continue
        m = stamp_re.search(lines[stamp_line_idx])
        start_ms = parse_ms(m.group(1))
        end_ms = parse_ms(m.group(2))
        text_lines = lines[stamp_line_idx + 1:]
        text = " ".join([t.strip() for t in text_lines if t.strip()])
        duration_s = max(0.1, (end_ms - start_ms) / 1000.0)

        subs.append({
            "index": idx,
            "start": m.group(1).replace(".", ","),
            "end": m.group(2).replace(".", ","),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration": duration_s,
            "text": text,
        })
        idx += 1
    return subs

def format_srt_content(subs: list) -> str:
    out = []
    for i, s in enumerate(subs, 1):
        out.append(f"{i}\n{s['start']} --> {s['end']}\n{s['text']}\n")
    return "\n".join(out).strip() + "\n"

class TranslationProgressManager:
    def __init__(self, workspace_dir: str, target_lang: str = "Tiếng Việt"):
        self.workspace_dir = str(workspace_dir)
        self.data_dir = os.path.join(self.workspace_dir, "Data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.progress_file = os.path.join(self.data_dir, "temp_translation_progress.json")
        self.out_srt_file = os.path.join(self.data_dir, "temp_translated.srt")
        self.target_lang = str(target_lang or "Tiếng Việt").strip()
        self.translations = {} # int index -> str translated text

    def load_progress(self, subtitles: list) -> Tuple[Dict[int, str], List[int]]:
        total_subs = len(subtitles)
        self.translations = {}

        # 1. Try reading checkpoint file
        if os.path.isfile(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("total_subs") == total_subs and str(data.get("target_lang")).strip().lower() == self.target_lang.lower():
                    raw_tr = data.get("translations", {})
                    for k, v in raw_tr.items():
                        if v and str(v).strip():
                            self.translations[int(k)] = str(v).strip()
            except Exception:
                pass

        # 2. Fallback to existing temp_translated.srt if valid
        if not self.translations and os.path.isfile(self.out_srt_file):
            try:
                with open(self.out_srt_file, "r", encoding="utf-8-sig", errors="replace") as f:
                    c = f.read()
                existing_subs = parse_srt_subtitles(c)
                if len(existing_subs) == total_subs:
                    for i, es in enumerate(existing_subs):
                        t = es.get("text", "").strip()
                        orig_t = subtitles[i].get("text", "").strip()
                        if t and t != orig_t:
                            self.translations[i] = t
            except Exception:
                pass

        missing_indices = [i for i in range(total_subs) if i not in self.translations]
        return self.translations, missing_indices

    def save_chunk(self, indices: list, lines: list, subtitles: list):
        for idx, line in zip(indices, lines):
            if line and line.strip():
                self.translations[idx] = line.strip()

        # Atomic write to progress_file
        cp_data = {
            "total_subs": len(subtitles),
            "target_lang": self.target_lang,
            "updated_at": time.time(),
            "completed_count": len(self.translations),
            "translations": {str(k): v for k, v in self.translations.items()}
        }
        tmp_json = self.progress_file + ".tmp"
        try:
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(cp_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_json, self.progress_file)
        except Exception:
            pass

        # Also write current progress into temp_translated.srt
        self._flush_srt(subtitles)

    def _flush_srt(self, subtitles: list):
        try:
            curr_subs = []
            for i, s in enumerate(subtitles):
                item = dict(s)
                item["text"] = self.translations.get(i, s.get("text", ""))
                curr_subs.append(item)
            tmp_srt = self.out_srt_file + ".tmp"
            with open(tmp_srt, "w", encoding="utf-8") as f:
                f.write(format_srt_content(curr_subs))
            os.replace(tmp_srt, self.out_srt_file)
        except Exception:
            pass

    def mark_completed(self, subtitles: list):
        self._flush_srt(subtitles)
        try:
            cp_data = {
                "total_subs": len(subtitles),
                "target_lang": self.target_lang,
                "completed": True,
                "updated_at": time.time(),
                "completed_count": len(self.translations),
                "translations": {str(k): v for k, v in self.translations.items()}
            }
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(cp_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear(self):
        self.translations = {}
        try:
            if os.path.isfile(self.progress_file):
                os.remove(self.progress_file)
        except Exception:
            pass
        try:
            if os.path.isfile(self.out_srt_file):
                os.remove(self.out_srt_file)
        except Exception:
            pass

def get_workspace_translation_status(workspace_dir: str) -> Tuple[int, int]:
    """Returns (completed_count, total_count). If no srt, returns (0, 0)"""
    try:
        data_dir = os.path.join(str(workspace_dir), "Data")
        orig_srt = os.path.join(data_dir, "temp_original.srt")
        if not os.path.isfile(orig_srt):
            return 0, 0
        with open(orig_srt, "r", encoding="utf-8-sig", errors="replace") as f:
            subs = parse_srt_subtitles(f.read())
        total = len(subs)
        if total == 0:
            return 0, 0

        cp_file = os.path.join(data_dir, "temp_translation_progress.json")
        if os.path.isfile(cp_file):
            with open(cp_file, "r", encoding="utf-8") as f:
                cp = json.load(f)
            return len(cp.get("translations", {})), total

        trans_srt = os.path.join(data_dir, "temp_translated.srt")
        if os.path.isfile(trans_srt):
            with open(trans_srt, "r", encoding="utf-8-sig", errors="replace") as f:
                t_subs = parse_srt_subtitles(f.read())
            if len(t_subs) == total:
                c = sum(1 for i, ts in enumerate(t_subs) if ts.get("text", "").strip() and ts.get("text", "").strip() != subs[i].get("text", "").strip())
                return c, total
    except Exception:
        pass
    return 0, 0
