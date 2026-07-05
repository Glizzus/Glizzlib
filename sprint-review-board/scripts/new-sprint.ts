/**
 * Creates the next sprint YAML file under yaml/.
 *
 * The next sprint number is derived from the highest existing sprint-<n>.yaml
 * in yaml/. When none exist, the sequence is bootstrapped at BOOTSTRAP_SPRINT.
 * Generated files conform to sprint.schema.json and carry a yaml-language-server
 * modeline so editors validate them against the schema.
 *
 * Run: npm run new-sprint
 */
import { mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const BOOTSTRAP_SPRINT = 4

const scriptDir = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(scriptDir, '..')
const yamlDir = join(projectRoot, 'yaml')
const schemaPath = join(projectRoot, 'sprint.schema.json')

const SPRINT_FILE = /^sprint-(\d+)\.yaml$/

function latestSprint(): number | null {
  let dirEntries: string[]
  try {
    dirEntries = readdirSync(yamlDir)
  } catch {
    // yaml/ doesn't exist yet — nothing to read.
    return null
  }

  const numbers = dirEntries
    .map((name) => name.match(SPRINT_FILE))
    .filter((m): m is RegExpMatchArray => m !== null)
    .map((m) => Number(m[1]))

  return numbers.length > 0 ? Math.max(...numbers) : null
}

function template(sprint: number, schemaRef: string): string {
  return `# yaml-language-server: $schema=${schemaRef}
sprint: ${sprint}
dates: "TODO: e.g. Jun 23 – Jul 4, 2026"
agenda:
  - "TODO: first agenda beat"
demos: []
`
}

const latest = latestSprint()
const next = latest === null ? BOOTSTRAP_SPRINT : latest + 1

mkdirSync(yamlDir, { recursive: true })

const outPath = join(yamlDir, `sprint-${next}.yaml`)
// posix-style relative path for the schema modeline, stable across editors.
const schemaRef = relative(yamlDir, schemaPath).split('\\').join('/')

writeFileSync(outPath, template(next, schemaRef), { flag: 'wx' })

console.log(
  `Created ${relative(projectRoot, outPath)}` +
    (latest === null ? ` (bootstrapped at sprint ${BOOTSTRAP_SPRINT})` : ` (after sprint ${latest})`),
)
