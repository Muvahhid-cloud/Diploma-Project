# Architectural Knowledge (Phase 3.5)

Status: **K1 implemented (v0.1)** · Code: `apps/api/app/modules/catalog/` · Data: `data/knowledge/`

Phase 3.5 grounds BuildAI in structured, source-attributed architectural knowledge. K1 is the
foundation: schemas, provenance, the first packs, loading, integrity and hash locking. **Nothing
consumes knowledge yet**: no engine, validator, prompt or API reads it (import-linter contract
"K1: no module consumes the knowledge catalog yet").

| Step | Scope | Status |
|---|---|---|
| **K1** Knowledge Foundation | catalog module, provenance, ontology, glossary, drawing profile, region-profile foundation, loader, registry, integrity, lock, first packs | ☑ |
| K2 Families, Types, Assemblies | typed door/window/wall/floor/roof/stair families and layered assemblies | ☐ |
| K3 Design Systems | coherent combinations of types, assemblies, roofs, finishes, openings | ☐ |
| K4 Templates | real building configurations (programme, relationships, circulation, constraints) | ☐ |
| K5 Knowledge API and Units | read-only catalog API; imperial display/input conversion | ☐ |
| K6 Optional Structural Elements | structural element types in the model | ☐ |

## 1. Principles

1. **Knowledge is not rules.** Knowledge describes; rules constrain. Enforceable minimums and
   maximums live only in `BuildingRulesProfile`s (`data/rules-profiles/`, CLAUDE.md rule 16).
   If knowledge should ever constrain a design, a rules-profile entry is created for it.
2. **Every object is attributed.** At least one citation to a source record, with printed page
   numbers for paginated sources.
3. **Only `approved` knowledge may be consumed** by engines or AI (`registry.approved_items()`),
   and approval requires a human review record. In K1 nothing is approved.
4. **Paraphrase only.** No quotations, reproduced figures, symbols or tables beyond parameters.
   Source documents are never committed; source records keep a SHA-256 fingerprint.
5. **Global vs scoped.** The `core` pack is region- and practice-independent. It may cite a
   published source only for the *existence* of a concept. Source-specific statements live in
   scoped packs (a drawing-convention profile or a region).
6. **The building model stays canonical.** The ontology *binds to* the Pydantic vocabulary and
   never replaces it (CLAUDE.md rule 7).
7. **Versioned and locked.** Packs are immutable once used (new `.v<n>` directory for changes);
   every data change needs `pnpm knowledge:lock`.

## 2. Sources

`data/knowledge/sources/<id>.yaml` holds one `Source` per document:

| Field | Meaning |
|---|---|
| `kind` | `reference_handbook`, `standard` or `editorial` (BuildAI-authored content) |
| `title`, `authors`, `publisher`, `publication_year`, `isbn`, `language` | bibliography |
| `page_count` | printed pages; citations must fall inside it (`null` = not paginated) |
| `basis`, `jurisdiction_context`, `temporal_note`, `scope_note` | what the source is and is not |
| `artifact` | format, `sha256`, artifact page count, page map; `stored_in_repo` is always false |
| `usage_policy` | `paraphrase_only: true`, `reproduce_figures: false` for published sources |

Current sources:

- **`georgievsky-2004`**: Георгиевский О.В., *Единые требования по выполнению строительных
  чертежей* (Архитектура-С, 2004, 144 pp.). A student reference handbook that, by its preface,
  follows ESKD/SPDS as of 2004. It is **one** source, scoped as the `spds` drawing-convention
  profile, **not** a global architectural standard and not a construction-code engine. It is
  mostly drafting conventions; it contains almost no room-programme or layout guidance.
- **`buildai-editorial`**: our own ontology structure, IFC mappings, English terms and
  definitions, and model bindings.

## 3. Packs

```
data/knowledge/
├── knowledge.lock.json
├── sources/{georgievsky-2004,buildai-editorial}.yaml
├── packs/
│   ├── core.v1/                      scope: global
│   │   ├── pack.yaml
│   │   ├── ontology.yaml             79 classes, 9 relationship definitions
│   │   └── glossary.en.yaml          60 canonical terms
│   └── spds-georgievsky-2004.v1/     scope: drawing_convention_profile (spds), depends on core@1
│       ├── pack.yaml
│       ├── model.yaml  layout.yaml  drawing-sheets.yaml  drawing-views.yaml
│       ├── structural.yaml  mep.yaml  reference.yaml   (89 knowledge items)
│       ├── glossary.ru.yaml          59 Russian wordings of core terms
│       └── drawing-profile.yaml      the spds@1 drawing profile
└── regions/generic.v1.yaml
```

A **pack manifest** (`pack.yaml`) declares `id`, `version`, `status`, `scope`
(`global` | `drawing_convention_profile` | `regional`, with jurisdiction and era), the `sources`
it may cite, `depends_on` (pack refs) and `contents`, which lists **every** file (unlisted or
missing files are errors).

### 3.1 Knowledge items

```yaml
- id: drawing.plan.cut_plane          # dotted, unique per pack; ref = spds-georgievsky-2004@1:drawing.plan.cut_plane
  kind: convention                    # principle|convention|definition|code_list|content_list|
                                      # dimension_table|symbol_set|example|reference
  category: drawing                   # building_model|layout|drawing|structural_drawing|mep|reference
  concept: floor plan cutting plane
  statement: >-                       # paraphrase, <= 500 characters
    A floor plan is a horizontal section at the level of the window openings or at one third ...
  params: { cut_height_of_storey_ratio: 0.333 }
  inferences: []                      # anything NOT stated by the source
  confidence: high                    # high|medium|low
  usage: runtime_candidate            # or reference_only (never consumed)
  intended_use: [documentation.plan.cut]
  related: [term.floor_plan]          # class./term. ids or items of the same pack
  provenance: [{ source: georgievsky-2004, pages: [69], section: "6.2", figures: ["Рис. 76"] }]
  status: extracted
```

**Units:** every numeric parameter carries a unit through its own or an enclosing key suffix:
`_m`, `_m2` (building space, SI), `_paper_mm` (drawing sheet), `_deg`, `_ratio`, `_s` (multiples
of the main line thickness), `_count`, `_index`. Scales are quoted ratios (`"1:100"`); an
unquoted YAML `1:10` would parse as a number. Imperial conversion is a K5 display/input layer;
internal values stay SI.

`kind: example` marks values shown in a worked example (e.g. a slope on an illustration). They
are always `reference_only` and never rules.

### 3.2 Ontology (`core`)

- `OntologyClass`: `id` (`class.*`), English `label`, `kind` (building, storey, element, space,
  grid, system), `parent` (is-a), `model_binding`, `ifc` (entity + predefined type, editorial),
  `in_scope_v1` (residential, ≤ 3 storeys).
- `model_binding` targets exactly one of `element_type`, `room_type`, `building_type` or
  `level`, optionally with a `discriminator`/`value` (e.g. `wall_kind: partition`).
- **Coverage invariant:** every element type, room type, building type, the level, and every
  `RelationshipKind` is bound by exactly one primary class or relationship definition. A model
  vocabulary change without an ontology update fails the integrity check.
- `RelationshipDefinition`: `model_binding` (a `RelationshipKind`), allowed `source_classes` /
  `target_classes` (subclasses included), `per_source` cardinality, `reserved` for Phase 6 MEP.
- Unbound classes (foundation, lintel, column, pipeline, …) are vocabulary only. K1 introduces
  no model element types.

### 3.3 Glossary

`Term` (core): canonical id `term.*`, English `preferred`, `synonyms`, editorial `definition`,
`class_ref`. `LocalizedTerm` (scoped packs): `term_id`, `locale`, `preferred`, `synonyms`,
`abbreviations`, `codes` (e.g. `spds_letter: ПР`), each cited to the page where the source
uses the term.

## 4. Drawing profiles

A `DrawingProfile` (`spds@1`) is a versioned grouping of a pack's drawing items by topic (sets,
sheets, scales, lines, fonts, hatching, dimensions, axes, level marks, callouts, titles, views,
symbols, site) for future documentation generation. It must live in a
`drawing_convention_profile` pack scoped to its id, every topic reference must be a drawing item
of that pack, and every drawing item must be grouped. Symbols are stored as meanings and
parameters (e.g. door kinds, sash kinds, arrow semantics), never as glyphs. Another practice
(ISO, a regional standard) is a separate profile over separate knowledge.

## 5. Region profiles

`RegionProfile` composes regional choices **by reference**: `rules_profile`
(e.g. `generic-residential@1`), optional `drawing_profile`, `knowledge_packs`, `locales`,
`measurement` (internal SI; display metric until K5), `region_codes` (ISO 3166, empty =
region-independent). It holds no rules or knowledge itself. `generic@1` is the default and
deliberately does **not** include the SPDS pack; a region opts into a drawing profile
explicitly (and must then include the pack that defines it). Nothing reads region profiles
until later steps.

## 6. Lifecycle

| Status | Meaning | Allowed |
|---|---|---|
| `draft` | team-authored, unreviewed | editorial citations only |
| `extracted` | taken from a published source, unreviewed | needs a published-source citation |
| `needs_verification` | extracted, with legibility or interpretation doubts | same |
| `reviewed` | checked against the cited pages by a person | needs `review {reviewed_by, reviewed_on}` |
| `approved` | released for runtime use | needs `review`; not with `confidence: low` |
| `deprecated` | kept for provenance | may carry `superseded_by` |

In K1 all book-derived objects are `extracted` (83 items) or `needs_verification` (6: the window,
door and fixture size tables, minimum line thickness, pipeline codes, the standards list).
Twenty items are `reference_only` (structural drawing, bibliographic, examples).

## 7. Loading, integrity and lock

`catalog.loader.read_knowledge(data_dir)` parses every document (Pydantic, `extra="forbid"`),
builds the `KnowledgeRegistry`, runs `integrity.check_registry` and verifies the lock; any error
raises `KnowledgeLoadError` with all issues in the shared `Issue` shape (JSON-pointer paths).
`load_knowledge(data_dir)` is the cached variant.

Integrity checks: pack directory naming, unlisted/missing files, unknown sources and
dependencies, dependency cycles, duplicate ids; citation sources, declared sources, page ranges;
status ↔ source kind; global-scope borrowing; unit suffixes; scale format; approved
low-confidence items; unresolved `related`/`superseded_by`; class parents and cycles; binding
targets; relationship classes; ontology coverage; glossary links; drawing-profile scope, topic
references and grouping; region references (rules profile file, drawing profile, packs).

`knowledge.lock.json` stores a SHA-256 per source file, pack directory and region file
(LF-normalised, path-sorted). A stale, missing, unlisted or orphaned entry is an error.
Workflow: edit data → run tests → `pnpm knowledge:lock` → commit data and lock together.

## 8. What K1 does not do

No K2–K6 content, no retrieval layer or vector search, no costing, no API, no changes to the
layout engine, specification, model schema, prompts or generated contracts. Phase 1–3
behaviour is unchanged (golden files and `packages/schema` are byte-identical).

## 9. Known limitations

- Book items are unreviewed. Several tables were read from a low-resolution scan; the book's
  cited standards may have been superseded since 2004.
- The book offers almost no room-programme knowledge; templates (K4) need other sources.
- IFC mappings and English definitions are editorial and unreviewed (`draft`).
- `params` are typed JSON values checked for units; typed per-kind schemas arrive with K2.
