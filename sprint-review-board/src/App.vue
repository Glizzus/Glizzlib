<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

interface Sprint {
  sprint: number
  dates: string
  agenda: string[]
  demos: { topic: string; who: string }[]
}

// Latest sprint-<n>.yaml under yaml/ wins. Add files with `npm run new-sprint`.
const files = import.meta.glob('../yaml/sprint-*.yaml', { eager: true, import: 'default' })
const board = (Object.values(files) as Sprint[]).sort((a, b) => b.sprint - a.sprint)[0]

function toggleFull() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen()
  else document.exitFullscreen()
}

function onKey(e: KeyboardEvent) {
  if ((e.key === 'f' || e.key === 'F') && !e.metaKey && !e.ctrlKey) toggleFull()
}

// Hide the cursor while idle — this runs on a meeting-room screen.
let idle: ReturnType<typeof setTimeout> | undefined
function wake() {
  document.documentElement.style.cursor = ''
  clearTimeout(idle)
  idle = setTimeout(() => {
    document.documentElement.style.cursor = 'none'
  }, 2600)
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('mousemove', wake)
  wake()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('mousemove', wake)
  clearTimeout(idle)
  document.documentElement.style.cursor = ''
})
</script>

<template>
  <div v-if="!board" class="stage">
    <p class="empty">No sprint files found — run <code>npm run new-sprint</code>.</p>
  </div>

  <div v-else class="stage">
    <div class="page">
      <header>
        <!-- Project logo -->
        <svg viewBox="0 0 470 120" class="logo" role="img" aria-label="Helios — project logo">
          <g stroke="currentColor" stroke-width="7" stroke-linecap="round">
            <circle cx="58" cy="60" r="23" fill="none" />
            <line v-for="deg in [0, 45, 90, 135, 180, 225, 270, 315]" :key="deg" x1="58" y1="10" x2="58" y2="24" :transform="`rotate(${deg} 58 60)`" />
          </g>
          <text x="110" y="62" dominant-baseline="central" font-size="74" font-weight="600" letter-spacing="-2" fill="currentColor">Helios</text>
        </svg>

        <div class="sprint-meta">
          <div class="sprint-num"><span>Sprint </span><strong>{{ board.sprint }}</strong></div>
          <div class="sprint-dates">{{ board.dates }}</div>
        </div>
      </header>

      <main>
        <section>
          <div class="section-label agenda-label">Agenda</div>
          <div class="agenda">
            <div v-for="(item, i) in board.agenda" :key="i" class="agenda-item">
              <span class="agenda-num">{{ i + 1 }}</span>
              <span class="agenda-text">{{ item }}</span>
            </div>
          </div>
        </section>

        <section>
          <div class="section-label">Dev demos</div>
          <div v-for="(d, i) in board.demos" :key="i" class="demo">
            <div class="demo-topic">{{ d.topic }}</div>
            <div class="demo-who">{{ d.who }}</div>
          </div>
        </section>
      </main>

      <footer>
        <!-- Department logo -->
        <svg viewBox="0 0 300 40" class="dept-logo" role="img" aria-label="Platform Engineering — department logo">
          <g stroke="currentColor" stroke-width="3.5" fill="none">
            <rect x="4" y="7" width="26" height="26" rx="6" />
            <line x1="12" y1="25" x2="12" y2="18" />
            <line x1="17" y1="25" x2="17" y2="14" />
            <line x1="22" y1="25" x2="22" y2="20" />
          </g>
          <text x="44" y="21" dominant-baseline="central" font-size="19" font-weight="600" letter-spacing="0.2" fill="currentColor">Platform Engineering</text>
        </svg>
      </footer>
    </div>

    <button class="fullscreen" title="Fullscreen (F)" @click="toggleFull"><span>⤢</span> Fullscreen</button>
  </div>
</template>

<style>
.stage {
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.empty {
  color: var(--muted);
  font-size: 18px;
}

.page {
  width: 100%;
  max-width: clamp(680px, 84vw, 1140px);
  display: flex;
  flex-direction: column;
  padding: clamp(24px, 4.5vh, 64px) 0 clamp(16px, 2.5vh, 32px);
}

header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 48px;
  padding-bottom: clamp(22px, 3.4vh, 44px);
}

.logo {
  height: clamp(50px, 8vw, 112px);
  width: auto;
  display: block;
  color: var(--ink);
}

.sprint-meta {
  text-align: right;
  flex-shrink: 0;
  padding-bottom: 6px;
}

.sprint-num {
  font-size: clamp(20px, 2vw, 34px);
  letter-spacing: -0.01em;
}
.sprint-num span {
  color: var(--muted);
}
.sprint-num strong {
  font-weight: 500;
}

.sprint-dates {
  margin-top: 6px;
  font-size: clamp(13px, 1.05vw, 18px);
  color: var(--faint);
}

main {
  display: grid;
  grid-template-columns: clamp(220px, 26vw, 360px) 1fr;
  gap: clamp(40px, 6vw, 110px);
  border-top: 1px solid var(--line);
  padding-top: clamp(24px, 3.6vh, 52px);
}

.section-label {
  font-size: clamp(12px, 0.95vw, 15px);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-weight: 600;
  margin-bottom: clamp(6px, 1vh, 14px);
}
.agenda-label {
  margin-bottom: clamp(14px, 2vh, 26px);
}

.agenda {
  display: flex;
  flex-direction: column;
  gap: clamp(9px, 1.5vh, 18px);
}

.agenda-item {
  display: flex;
  gap: 14px;
  align-items: baseline;
}

.agenda-num {
  font-size: clamp(13px, 1vw, 17px);
  color: var(--faint);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.agenda-text {
  font-size: clamp(16px, 1.35vw, 24px);
  line-height: 1.32;
  text-wrap: pretty;
}

.demo {
  padding: clamp(10px, 1.9vh, 24px) 0;
}

.demo-topic {
  font-size: clamp(19px, 1.6vw, 31px);
  font-weight: 500;
  letter-spacing: -0.01em;
  line-height: 1.14;
  text-wrap: pretty;
}

.demo-who {
  margin-top: clamp(4px, 0.7vh, 9px);
  font-size: clamp(14px, 1.05vw, 18px);
  color: var(--muted);
}

footer {
  margin-top: clamp(16px, 3vh, 48px);
}

.dept-logo {
  height: clamp(18px, 1.7vw, 26px);
  width: auto;
  display: block;
  color: var(--muted);
  opacity: 0.7;
}

.fullscreen {
  position: absolute;
  bottom: clamp(16px, 2.4vh, 30px);
  right: clamp(20px, 2.4vw, 36px);
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: transparent;
  border: none;
  color: var(--faint);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  padding: 6px;
}
.fullscreen:hover {
  color: var(--muted);
}
.fullscreen span {
  font-size: 15px;
  line-height: 1;
}
</style>
