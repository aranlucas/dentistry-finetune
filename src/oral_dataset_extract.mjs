// Read-only extraction using Oral Boards' own parsers. No app/search/API imports.
import fs from 'node:fs';
import path from 'node:path';
import {registerHooks} from 'node:module';
import {pathToFileURL, fileURLToPath} from 'node:url';

const root = path.resolve(process.argv[2]);
registerHooks({resolve(specifier, context, next) {
  let request = specifier;
  if (specifier.startsWith('@/')) request = pathToFileURL(path.join(root, specifier.slice(2))).href;
  try {return next(request, context);} catch (error) {
    if (error.code !== 'ERR_MODULE_NOT_FOUND' || !context.parentURL) throw error;
    if (!request.startsWith('.') && !request.startsWith('file:')) throw error;
    const base = request.startsWith('file:') ? fileURLToPath(request)
      : path.resolve(path.dirname(fileURLToPath(context.parentURL)), request);
    for (const extension of ['.ts', '.tsx', '.js']) {
      if (fs.existsSync(base + extension)) return next(pathToFileURL(base + extension).href, context);
    }
    throw error;
  }
}});
const get = name => import(pathToFileURL(path.join(root, name)).href);
const {parseMarkdownFrontmatter} = await get('lib/markdown-frontmatter.ts');
const {parseFlashcardMarkdown} = await get('lib/flashcard-markdown.ts');
const {parseMedicalConditionMarkdown} = await get('lib/medical-condition-markdown.ts');
const {parseCaseMarkdown} = await get('lib/case-markdown.ts');
const {parseStudyThemeMarkdown} = await get('lib/study-theme-markdown.ts');
const {pathwayFlashcards} = await get('lib/pathway-flashcards.ts');
const {parseMarkdown} = await get('lib/markdown-parser.ts');
const {pdfSources} = await get('data/study-sources.ts');
const output = {files: [], rows: [], errors: [], parserFiles: [
  'lib/markdown-frontmatter.ts', 'lib/flashcard-markdown.ts',
  'lib/medical-condition-markdown.ts', 'lib/case-markdown.ts',
  'lib/study-theme-markdown.ts', 'lib/pathway-flashcards.ts',
  'lib/markdown-parser.ts', 'lib/markdown-text.ts', 'lib/mermaid-source.ts',
  'data/study-sources.ts', 'data/medical-conditions.ts']};
const sources = Object.fromEntries(pdfSources.map(s => [s.id, s]));
const text = node => node.value ?? node.children?.map(text).join('') ?? '';
function sections(markdown) {
  const headings = parseMarkdown(markdown).children.filter(n => n.type === 'heading' && n.depth === 2);
  return headings.map((h, i) => ({heading: text(h),
    body: markdown.slice(h.position.end.offset, headings[i + 1]?.position.start.offset).trim(),
    start: h.position.start.offset, end: headings[i + 1]?.position.start.offset ?? markdown.length}));
}
function files(directory) {
  return fs.readdirSync(path.join(root, directory)).filter(n => n.endsWith('.mdx')).sort()
    .map(n => path.join(directory, n));
}
function add(file, kind, question, answer, references, extra = {}) {
  if (!question.trim() || !answer.trim()) return;
  output.rows.push({file, kind, question: question.trim(), answer: answer.trim(), references, ...extra});
}
function read(file, category, run) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  output.files.push({path: file, category});
  try {run(source);} catch (error) {output.errors.push({file, error: String(error.message)});}
}
for (const file of files('content/aapd-notes')) read(file, 'aapd_note', raw => {
  const {data, content} = parseMarkdownFrontmatter(raw, 'Missing note metadata');
  const refs = [{title: data.title, url: data.pdf_url, revision: data.source_revision}];
  for (const section of sections(content)) {
    if (/^(sources?|references?|further reading)$/i.test(section.heading)) continue;
    const question = section.heading.endsWith('?') ? section.heading
      : `In the study notes on ${data.title}, what does the section “${section.heading}” explain?`;
    add(file, 'note_section', question, section.body, refs,
      {heading: section.heading, title: data.title, derivation: 'whole_section_extraction',
       evidence: {kind: 'authored_study_section', text: section.body,
         location: {heading: section.heading, offsets_in_frontmatter_body: [section.start, section.end]}}});
  }
  for (const id of data.flashcards ?? []) {
    if (!/^aapd-notes\/[a-z0-9_-]+$/.test(id)) throw new Error('Unexpected deck path');
    const deckFile = 'content/flashcards/' + id + '.mdx';
    read(deckFile, 'aapd_flashcard', deckRaw => {
      const deck = parseFlashcardMarkdown(deckRaw);
      if (deck.metadata.source !== '/notes/' + path.basename(file, '.mdx')) throw new Error('Deck source mismatch');
      for (const card of deck.cards) add(deckFile, 'flashcard', card.front, card.back, refs,
        {title: data.title, related_files: [file], derivation: 'existing_question_answer',
         evidence: {kind: 'authored_flashcard', text: card.back}});
    });
  }
});
for (const file of files('content/medical-conditions')) read(file, 'medical_condition', raw => {
  const {metadata, cards, markdown} = parseMedicalConditionMarkdown(raw);
  for (const card of cards) add(file, 'condition_card', card.front, card.back, metadata.sources,
    {title: metadata.name, derivation: 'existing_question_answer',
     evidence: {kind: 'authored_condition_answer', text: card.back}});
  for (const section of sections(markdown).filter(s => /^(overview|exam pearl)$/i.test(s.heading))) {
    add(file, 'condition_summary', `Summarize the ${section.heading.toLowerCase()} for ${metadata.name} from the study notes.`,
      section.body, metadata.sources, {title: metadata.name, heading: section.heading,
        derivation: 'whole_section_extraction', evidence: {kind: 'authored_condition_section', text: section.body}});
  }
});
for (const file of files('content/study-themes')) read(file, 'study_theme', raw => {
  const {theme} = parseStudyThemeMarkdown(raw);
  const refs = evidence => evidence.map(e => ({...sources[e.source], url: sources[e.source].href, pages: e.pages}));
  const common = {title: theme.title, derivation: 'existing_question_answer'};
  for (const d of theme.decisions) add(file, 'theme_decision', d.question, d.answer, refs(d.evidence),
    {...common, authored_id: d.id, evidence: {kind: 'authored_theme_decision', text: d.answer}});
  for (const p of theme.points) add(file, 'theme_point', `What does the study theme “${theme.title}” teach about this point?\n\n${p.text.split(/(?<=[.!?])\s/)[0]}`,
    p.text, refs(p.evidence), {title: theme.title, derivation: 'extractive_teaching_point',
      needs_question_rewrite: true, evidence: {kind: 'authored_theme_point', text: p.text}});
  for (const r of theme.recapRules) add(file, 'theme_recap', `${r.question}\n\nConditions: ${r.when}`,
    r.say, theme.sourceIds.map(id => ({...sources[id], url: sources[id].href})),
    {...common, authored_id: r.id, broad_source_mapping: true,
     evidence: {kind: 'authored_theme_recap', text: r.say}});
  for (const card of pathwayFlashcards(theme)) add(file, 'theme_pathway', card.front, card.back, refs(card.evidence),
    {...common, authored_id: card.id, derivation: 'authored_pathway_rendering',
     evidence: {kind: 'authored_conditional_pathway', text: card.back}});
});
for (const file of files('content/cases')) read(file, 'case', raw => {
  const c = parseCaseMarkdown(path.basename(file, '.mdx'), raw);
  const presentation = c.slides.map(s => `${s.title}\n${s.builds.join('\n\n')}`).join('\n\n');
  const questions = {diagnosis: 'What diagnosis is supported?', differentialDiagnosis: 'What alternatives should be ruled out?',
    treatmentPlan: 'What treatment plan is described?', rationale: 'What is the rationale?', keyPoints: 'What key points should the study answer include?'};
  for (const [key, q] of Object.entries(questions)) {
    const value = c.modelResponse[key]; if (!value) continue;
    const base = Array.isArray(value) ? value.map(v => '- ' + v).join('\n') : value;
    const answer = base + (c.modelResponse.supplements?.[key] ? '\n\n' + c.modelResponse.supplements[key] : '');
    add(file, 'case_' + key, `Study case: ${c.title}\n\nComplete available presentation:\n${presentation}\n\n${q}`,
      answer, c.references ?? [], {title: c.title, related_slugs: [...c.notes ?? [], ...c.conditions ?? []],
        derivation: 'authored_case_section', fictional_status: 'unverified',
        evidence: {kind: 'authored_case_model_response', text: answer, section: key},
        requires_case_review: true});
  }
});
process.stdout.write(JSON.stringify(output));
