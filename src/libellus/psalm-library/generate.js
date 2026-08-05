// On-demand psalm/Magnificat GABC generation from jgabc's psalm-tone engine
// (vendor/psalmtone.node.js, public domain, see vendor/LICENSE).
//
// Called by libellus (resolve.py) at build time; also usable by hand:
//
//   node generate.js list-toni
//     -> JSON array of the canonical tone labels, e.g. ["1D","1D2",...,"8G*"]
//
//   node generate.js verses --psalmus 109 --tonus "8G"
//   node generate.js verses --psalmus magnificat --tonus 1D
//     -> JSON {"folder": "8g", "verses": ["<full gabc file content>", ...]}
//        (Gloria Patri appended; the Magnificat intones every verse)
//
//   node generate.js verses --psalmus magnificat --tonus 1D --open-notes
//     -> the same, but every reciting note jgabc does not put a syllable on is
//        drawn as an open (hollow) note, the way the Liber Usualis prints a
//        tone. Only the Kurzfassung's two-verse Magnificat system needs this
//        (ADR-0022); ordinary booklet verses are generated closed.
//
//   node generate.js euouae
//     -> JSON {"8G": "j j i j h g.", "1f": "h h g f gh gf..", ...}: the
//        EUOUAE (termination cue) of every named ending, all written under
//        one canonical clef, c4 (issue #45). Mode plus differentia fully
//        determine these notes, so they are derived here, never
//        hand-supplied (issue #33).
//
// Tone labels are matched case-insensitively, ignoring spaces and dots, with
// "*" also spellable as "star" — so "8 G", "8g" and "8G" are the same tone.
// Unknown tone/psalm -> exit 2 with JSON {"error": ..., "toni": [...]}.

'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ---------------------------------------------------------------- jgabc load
// The vendored upstream source is executed byte-for-byte, unmodified, in a
// vm context; afterwards the few helpers upstream defines but does not
// export are read out of that context (they are plain `var`/`function`
// declarations, i.e. context globals).
const pt = (function loadPsalmtone() {
  const src = fs.readFileSync(path.join(__dirname, 'vendor', 'psalmtone.node.js'), 'utf8');
  const module_ = { exports: {} };
  const context = vm.createContext({
    module: module_, exports: module_.exports,
    // upstream requires jquery for its web fetcher only, which is never
    // called here — an empty stub satisfies the import
    require: () => ({}), console,
    // psalmtone schedules a delayed, network-backed word-list refresh that
    // plain-node runs never reach either — results are unaffected without it
    setTimeout: () => 0, clearTimeout: () => {},
  });
  vm.runInContext(src, context, { filename: 'vendor/psalmtone.node.js' });
  for (const name of ['g_tones', 'getGabcTones', 'removeIntonation', 'splitLine', 'gloria_patri']) {
    module_.exports[name] = context[name];
  }
  return module_.exports;
})();

// ------------------------------------------------------------------- tones
// The full Liber Usualis ferial tone set as defined by jgabc. `single: true`
// marks tones with only one termination; the label is the one the books
// print. (Not offered: jgabc's alternative tone-6 mediant "6 alt", solemn
// variants.)
const TONES = [
  { key: '1.', mode: '1', endings: ['D', 'D-', 'D2', 'f', 'g', 'g2', 'g3', 'a', 'a2', 'a3'] },
  { key: '2.', mode: '2', endings: ['D'], single: true },
  { key: '3.', mode: '3', endings: ['b', 'a', 'a2', 'g', 'g2'] },
  { key: '4.', mode: '4', endings: ['g', 'E'] },
  { key: '4 alt', mode: '4', endings: ['c', 'A', 'A*', 'd'] },
  { key: '5.', mode: '5', endings: ['a'], single: true },
  { key: '6.', mode: '6', endings: ['F'], single: true },
  { key: '7.', mode: '7', endings: ['a', 'b', 'c', 'c2', 'd'] },
  { key: '8.', mode: '8', endings: ['G', 'G*', 'c'] },
  { key: 'per.', mode: 'peregrinus', endings: [''], single: true },
];

// "8" + "G*" -> "8gstar"; peregrinus has no ending label -> "peregrinus".
function toneFolder(mode, ending) {
  if (mode === 'peregrinus') return 'peregrinus';
  return mode + ending.toLowerCase().replace('*', 'star');
}

function canonicalLabel(mode, ending) {
  return mode === 'peregrinus' ? 'peregrinus' : mode + ending;
}

function normalizeLabel(label) {
  return String(label).toLowerCase().replace(/[\s.]/g, '').replace('*', 'star');
}

function findTone(label) {
  const wanted = normalizeLabel(label);
  for (const tone of TONES) {
    for (const ending of tone.endings) {
      if (normalizeLabel(canonicalLabel(tone.mode, ending)) === wanted
        || toneFolder(tone.mode, ending) === wanted) {
        return { tone, ending };
      }
    }
  }
  return null;
}

function allLabels() {
  const labels = [];
  for (const tone of TONES) {
    for (const ending of tone.endings) labels.push(canonicalLabel(tone.mode, ending));
  }
  return labels;
}

// header form: "a2" -> "a 2" (as the hand-transcribed library files wrote it)
function differentiaLabel(ending) {
  return ending.replace(/(\d+)$/, ' $1');
}

// ------------------------------------------------------------------ euouae
// "EUOUAE" are the vowels of "sæculOrUm. AmEn" — so an ending's EUOUAE is
// simply the notes its termination formula puts on the last six syllables
// of the Gloria Patri's final verse. Deriving it that way (rather than
// reading the formula string) keeps jgabc as the single source of truth:
// the formula is an accent-aware template whose reciting tones absorb a
// variable number of syllables, so only the engine can say authoritatively
// which note lands where (issue #33).
const EUOUAE_SYLLABLES = 6;

// gabc pitch letters are staff *positions*, not notes: what they sound is
// decided by the clef, and the tone table uses three of them (c4, c3, f3).
// A EUOUAE is printed on the *antiphon's* stave, never on the verse stave it
// was derived from, so handing it out in the verse's clef leaves every
// consumer to guess; it is transposed into one canonical frame instead
// (issue #45). Mirrored by gabc.py's CANONICAL_CLEF.
const CANONICAL_CLEF = 'c4';

// The four staff lines, bottom to top, as staff positions: d f h j. A c clef
// marks "do" on its own line; an f clef marks "fa", three positions above
// "do" (do-re-mi-fa).
const LINE = [3, 5, 7, 9];

function doPosition(clef) {
  const m = /^([cf])(b?)([1-4])$/.exec(clef);
  if (!m) throw new Error(`unreadable clef "${clef}"`);
  // A flat lowers a pitch without moving a staff position, so gabc.py's
  // _do_position reads past one — it only ever *compares* positions. This is
  // the stricter job: rewriting notation out of a flat clef would silently
  // drop the flat, so refuse rather than guess. No tone uses one today.
  if (m[2]) throw new Error(`cannot transpose out of the flat clef "${clef}"`);
  const line = LINE[Number(m[3]) - 1];
  return m[1] === 'c' ? line : line - 3;
}

function underCanonicalClef(neumes, clef) {
  const shift = doPosition(CANONICAL_CLEF) - doPosition(clef);
  if (shift === 0) return neumes;
  return neumes.replace(/[a-mA-M]/g, (letter) => {
    const moved = letter.toLowerCase().charCodeAt(0) + shift;
    if (moved < 97 || moved > 109) {
      throw new Error(`"${neumes}" leaves the staff moving ${clef} -> ${CANONICAL_CLEF}`);
    }
    const canonical = String.fromCharCode(moved);
    return letter === letter.toLowerCase() ? canonical : canonical.toUpperCase();
  });
}

function euouaeOf(tone, ending) {
  const verses = generateVerses(pt.gloria_patri, tone, ending, false, false);
  const secondHalf = verses[verses.length - 1].split('*(:)')[1];
  const notes = [];
  const re = /\(([^)]*)\)/g;
  let m;
  while ((m = re.exec(secondHalf))) {
    if (/[a-mA-M]/.test(m[1])) notes.push(m[1]);
  }
  const euouae = notes.slice(-EUOUAE_SYLLABLES).join(' ');
  return underCanonicalClef(euouae, pt.g_tones[tone.key].clef);
}

function allEuouae() {
  const result = {};
  for (const tone of TONES) {
    for (const ending of tone.endings) {
      result[canonicalLabel(tone.mode, ending)] = euouaeOf(tone, ending);
    }
  }
  return result;
}

function deepCopyTones(t) {
  const copy = Object.create(Object.getPrototypeOf(t));
  Object.assign(copy, JSON.parse(JSON.stringify(t)));
  return copy;
}

// ------------------------------------------------------------- verse engine
// Mirrors the gabc branch of jgabc's psalmtone.html.js updateEditor().
function generateVerses(psalmText, tone, ending, repeatIntonation, openNotes) {
  const t = pt.g_tones[tone.key];
  const termLine = t.terminations ? t.terminations[ending] : (t.termination || t.mediant);
  let gMediant = pt.getGabcTones(t.mediant);
  const gTermination = pt.getGabcTones(termLine);
  const gShortMediant = pt.getGabcTones(t.shortMediant || t.solemn || t.mediant);

  const lines = psalmText.split('\n');
  const verses = [];
  let firstVerse = true;
  for (let i = 0; i < lines.length; ++i) {
    const line = pt.splitLine(lines[i]);
    const result = { shortened: false };
    let gabc = pt.applyPsalmTone({
      text: line[0].trim(),
      gabc: gMediant,
      useOpenNotes: !!openNotes,
      useBoldItalic: true,
      firstPrefix: true,
      onlyVowel: false,
      format: pt.bi_formats.gabc,
      verseNumber: i + 1,
      prefix: true,
      suffix: false,
      italicizeIntonation: false,
      result: result,
      gabcShort: gShortMediant,
      favor: firstVerse ? 'intonation' : '',
    });
    if (line.length > 1) {
      gabc += ' *(:) ' + pt.applyPsalmTone({
        text: line[1].trim(),
        gabc: gTermination,
        useOpenNotes: !!openNotes,
        useBoldItalic: true,
        firstPrefix: true,
        onlyVowel: false,
        format: pt.bi_formats.gabc,
        verseNumber: i + 1,
        prefix: false,
        suffix: true,
        italicizeIntonation: false,
        favor: 'termination',
      });
    }
    gabc = '(' + t.clef + ') ' + gabc + ' (::)';
    if (/undefined|NaN/.test(gabc)) {
      throw new Error(`bad gabc for verse ${i + 1} of tone ${tone.key} ${ending}: ${gabc}`);
    }
    verses.push(gabc);
    if (i === 0 && !repeatIntonation) gMediant = pt.removeIntonation(deepCopyTones(gMediant));
    if (!result.shortened) firstVerse = false;
  }
  return verses;
}

function verseFile(name, officePart, tone, ending, verseNumber, verse) {
  const header = [`name: ${name}, v. ${verseNumber};`, `office-part: ${officePart};`, `mode: ${tone.mode};`];
  if (tone.mode !== 'peregrinus' && !tone.single) {
    header.push(`mode-differentia: ${differentiaLabel(ending)};`);
  }
  return header.join('\n') + '\n%%\n' + verse + '\n';
}

// --------------------------------------------------------------------- CLI
function fail(payload) {
  process.stdout.write(JSON.stringify(payload) + '\n');
  process.exit(2);
}

function main(argv) {
  const command = argv[0];
  if (command === 'list-toni') {
    process.stdout.write(JSON.stringify(allLabels()) + '\n');
    return;
  }
  if (command === 'euouae') {
    process.stdout.write(JSON.stringify(allEuouae()) + '\n');
    return;
  }
  if (command !== 'verses') {
    fail({ error: `unknown command "${command || ''}" — use: list-toni | euouae | verses` });
  }
  const args = {};
  const flags = argv.slice(1).filter((a) => a === '--open-notes');
  const openNotes = flags.length > 0;
  const rest = argv.slice(1).filter((a) => a !== '--open-notes');
  for (let i = 0; i < rest.length; i += 2) args[rest[i].replace(/^--/, '')] = rest[i + 1];
  if (!args.psalmus || !args.tonus) {
    fail({ error: 'usage: verses --psalmus <1..150|magnificat> --tonus <label>' });
  }

  const found = findTone(args.tonus);
  if (!found) fail({ error: `unknown tone "${args.tonus}"`, toni: allLabels() });

  const isCanticle = args.psalmus.toLowerCase() === 'magnificat';
  // jgabc names the psalm files with three digits ("001.txt", "042.txt"), so
  // the number has to be padded to find them. Without this every psalm below
  // 100 reported "unknown psalm" — two thirds of the psalter — which stayed
  // hidden while only Pss 109-116 were ever sung from it.
  const number = isCanticle ? null : String(parseInt(args.psalmus, 10));
  const fileBase = isCanticle ? 'Magnificat' : number.padStart(3, '0');
  const textPath = path.join(__dirname, 'vendor', 'psalms', fileBase + '.txt');
  if (!/^(\d+|Magnificat)$/.test(fileBase) || !fs.existsSync(textPath)) {
    fail({ error: `unknown psalm "${args.psalmus}"` });
  }
  const text = fs.readFileSync(textPath, 'utf8').replace(/^﻿/, '').trim()
    + '\n' + pt.gloria_patri;

  // the printed name keeps the number unpadded: "Psalmus 42", not "Psalmus 042"
  const name = isCanticle ? 'Magnificat' : `Psalmus ${number}`;
  // canticle: the intonation is repeated on every verse
  const verses = generateVerses(text, found.tone, found.ending, isCanticle, openNotes)
    .map((verse, i) => verseFile(
      name, isCanticle ? 'Canticum' : 'Psalmus', found.tone, found.ending, i + 1, verse));
  process.stdout.write(JSON.stringify({
    folder: toneFolder(found.tone.mode, found.ending),
    verses: verses,
  }) + '\n');
}

main(process.argv.slice(2));
process.exit(0);
