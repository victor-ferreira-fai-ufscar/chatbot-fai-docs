/** Lógica de verificação de fundamentação/citação (espelha backend/eval/eval_manual_qa.py). */

import bases from "./data/manual-law-bases.json";

export const MANUAL_LAW_BASES: Set<string> = new Set(bases.bases);
export const N_PAGINAS: number = bases.n_paginas;

// Arquivos de manual conhecidos (normalizados). Aceita "Manual do Coordenador.pdf" e a
// forma com underscore "Manual_do_Coordenador.pdf" (normalizam igual).
export const KNOWN_FILES: Set<string> = new Set([normFile("Manual do Coordenador.pdf")]);

export function normFile(s: string): string {
  return (s || "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

const ABSTENTION_RE =
  /n[ãa]o\s+(consta|detalha|est[áa]|especifica|menciona|trata|aborda|foi poss|disp|h[áa] info)/i;
export const isAbstention = (text: string) => ABSTENTION_RE.test(text || "");

// Número-base de norma (antes do /ano) citado perto de uma palavra de lei.
const LEGAL_RE =
  /(?:Lei(?:\s+Complementar)?|Decreto(?:[-\s]?Lei)?|Resolu[çc][ãa]o|Portaria|Instru[çc][ãa]o\s+Normativa|Medida\s+Provis[óo]ria)[^.;:\n]{0,45}?(\d{1,4}(?:\.\d{1,3})*)\s*(?:\/\s*\d{2,4})?/gi;

export function citedLawBases(text: string): string[] {
  const out = new Set<string>();
  for (const m of (text || "").matchAll(LEGAL_RE)) out.add(m[1].replace(/\s/g, ""));
  return [...out];
}

// Nome de arquivo citado: "[arquivo.pdf, ...]" (inline) ou "- arquivo.pdf (pág...)" (chip).
export function citedFiles(answer: string, chipTexts: string[]): string[] {
  const out = new Set<string>();
  for (const m of (answer || "").matchAll(/\[([^[\]]+?\.pdf)[,\]]/gi)) out.add(m[1].trim());
  for (const c of chipTexts) {
    const m = c.match(/([^()·]+?\.pdf)/i);
    if (m) out.add(m[1].trim());
  }
  return [...out];
}

export function citedPages(answer: string, chipTexts: string[]): number[] {
  const out = new Set<number>();
  const blob = (chipTexts.join(" ") + " " + (answer || ""));
  for (const m of blob.matchAll(/p[áa]gs?\.?\s*([\d][\d\s,\-]*)/gi)) {
    for (const tok of m[1].split(/[,\s]+/)) {
      for (const part of tok.split("-")) {
        const n = parseInt(part, 10);
        if (!Number.isNaN(n)) out.add(n);
      }
    }
  }
  return [...out];
}

export interface Checks {
  fabricatedSources: string[];
  invalidPages: number[];
  fabricatedLaws: string[];
  grounded: boolean;
  abstention: boolean;
}

export function evaluateAnswer(answer: string, chipTexts: string[]): Checks {
  const files = citedFiles(answer, chipTexts);
  const pages = citedPages(answer, chipTexts);
  const laws = citedLawBases(answer);
  return {
    fabricatedSources: files.filter((f) => !KNOWN_FILES.has(normFile(f))),
    invalidPages: pages.filter((p) => p < 1 || p > N_PAGINAS),
    fabricatedLaws: laws.filter((b) => !MANUAL_LAW_BASES.has(b)),
    grounded: chipTexts.length > 0,
    abstention: isAbstention(answer),
  };
}
