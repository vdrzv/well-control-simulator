<template>
  <main class="page container-fluid">
    <header class="app-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div>
        <div class="eyebrow">Well control simulator</div>
        <h1 class="app-title">Drilling control room</h1>
      </div>
      <div class="header-actions d-flex align-items-center gap-2">
        <a v-if="pageData.user === 'admin'" class="admin-link" href="/admin/cases">Manage cases</a>
        <div class="run-state-controls" aria-label="Simulation state controls">
          <button
            type="button"
            class="state-control"
            :class="{ active: isPaused }"
            :disabled="stateControlsLocked"
            :aria-pressed="isPaused"
            @click="togglePause"
          >
            {{ isPaused ? 'Resume' : 'Pause' }}
          </button>
          <button
            type="button"
            class="state-control"
            :class="{ active: isFastForward }"
            :disabled="stateControlsLocked || isPaused"
            :aria-pressed="isFastForward"
            @click="toggleFastForward"
          >
            {{ isFastForward ? 'Normal speed' : 'Fast forward' }}
          </button>
          <button
            type="button"
            class="state-control finish-control"
            :disabled="stateControlsLocked"
            @click="finishRun"
          >
            Finish
          </button>
        </div>
        <div class="header-status d-flex align-items-center gap-2">
          <span class="status-dot" :class="`is-${runState}`" aria-hidden="true"></span>
          <span>{{ runStateLabel }}</span>
          <span class="header-divider"></span>
          <span>Case {{ currentCaseId ?? '—' }}</span>
          <span class="header-divider"></span>
          <span>Run {{ currentRunId ?? '—' }}</span>
          <span class="header-divider"></span>
          <span class="text-secondary">{{ pageData.user || 'Operator' }}</span>
        </div>
      </div>
    </header>

    <aside v-if="terminalMessage" class="run-result-banner" :class="`is-${runState}`" role="alert">
      <div>
        <strong>{{ runState === 'failed' ? 'Simulation failed' : 'Simulation finished' }}</strong>
        <span>{{ terminalMessage }}</span>
      </div>
      <a v-if="analysisUrl" :href="analysisUrl">Open case analysis</a>
    </aside>

    <div class="simulator-grid">
    <section class="choke-panel card">
      <div class="panel-heading">
        <div>
          <h2>Controls</h2>
        </div>
      </div>
      <div class="choke-inline-panel">
        <div class="control-section-heading">
          <span>Choke</span>
          <span class="value-badge">{{ chokePositionPercent }}% open</span>
        </div>
      <div class="choke-indicator">
        <div class="choke-indicator-head">
          <div class="choke-indicator-title">Position Indicator</div>
          <div class="choke-speed-heading">Choke Speed</div>
        </div>
        <div class="choke-indicator-body">
          <div class="choke-gauge-shell">
            <svg viewBox="0 0 220 160" class="choke-gauge">
              <path
                d="M 28 122 A 82 82 0 1 1 192 122"
                class="choke-gauge-arc"
              />
              <line
                v-for="tick in chokeGaugeTicks"
                :key="tick.value"
                :x1="tick.x1"
                :y1="tick.y1"
                :x2="tick.x2"
                :y2="tick.y2"
                class="choke-gauge-tick"
              />
              <text
                v-for="tick in chokeGaugeTicks"
                :key="`choke-label-${tick.value}`"
                :x="tick.lx"
                :y="tick.ly"
                text-anchor="middle"
                class="choke-gauge-label"
              >
                {{ tick.value }}
              </text>
              <line
                x1="110"
                y1="122"
                :x2="chokeNeedle.x"
                :y2="chokeNeedle.y"
                class="choke-gauge-needle"
              />
              <circle cx="110" cy="122" r="7" class="choke-gauge-center" />
              <text x="110" y="148" text-anchor="middle" class="choke-gauge-value">
                {{ chokePositionPercent }}%
              </text>
            </svg>
          </div>

          <fieldset class="choke-speed-panel">
            <span class="choke-speed-hint top">fastest</span>
            <label
              v-for="option in chokeSpeedOptions"
              :key="option"
              class="choke-speed-option form-check"
            >
              <input
                v-model="selectedChokeSpeed"
                type="radio"
                name="choke-speed"
                :value="option"
              />
              <span class="choke-speed-detent"></span>
            </label>
            <span class="choke-speed-hint bottom">slowest</span>
          </fieldset>
        </div>
      </div>

      <div class="choke-visual">
        <button
          type="button"
          class="choke-hit-area left btn"
          aria-label="Rotate choke left"
          @mousedown="setChokeDirection('left')"
          @mouseup="resetChoke"
          @mouseleave="resetChoke"
        ></button>
        <button
          type="button"
          class="choke-hit-area right btn"
          aria-label="Rotate choke right"
          @mousedown="setChokeDirection('right')"
          @mouseup="resetChoke"
          @mouseleave="resetChoke"
        ></button>
        <div class="choke-zone-label close">CLOSE</div>
        <div class="choke-zone-label open">OPEN</div>
        <div class="choke-slot"></div>
        <div class="choke-handle" :style="chokeHandleStyle">
          <span class="choke-knob"></span>
        </div>
      </div>
      </div>

      <div class="pump-inline-panel">
        <div class="control-section-heading">Pump</div>
        <div class="pump-metrics">
          <div class="pump-metric">
            <span class="pump-label">Total strokes</span>
            <strong>{{ formattedTotalStrokes }}</strong>
          </div>

          <div class="pump-metric">
            <span class="pump-label">Pump speed</span>
            <strong>{{ pumpSpeed }} spm</strong>
          </div>
        </div>

        <div class="pump-controls">
          <button type="button" class="pump-button btn btn-outline-light" @click="decreasePumpSpeed">−5</button>
          <div class="pump-regulator">+/- regulator</div>
          <button type="button" class="pump-button btn btn-warning" @click="increasePumpSpeed">+5</button>
        </div>

        <button
          type="button"
          class="mud-switch btn"
          :class="{ heavy: mudSwitch === 1 }"
          role="switch"
          :aria-checked="mudSwitch === 1"
          @click="toggleMudSwitch"
        >
          <span class="mud-switch-track"><i></i></span>
          <span>{{ mudSwitch === 1 ? 'Heavy mud' : 'Normal mud' }}</span>
        </button>
      </div>
    </section>

    <section class="annulus-panel card">
      <div class="annulus-header">
        <h2>Annulus</h2>
        <div class="pressure-summary">
          <span>Drillpipe: <b>{{ drillpipePressure }}</b></span>
          <span>Casing: <b>{{ casingPressure }}</b></span>
          <span>Ppl: <b>{{ formationPressure }}</b></span>
          <span>Pzab: <b>{{ bottomholePressure }}</b></span>
        </div>
      </div>

      <div class="annulus-legend">
        <span><i class="legend-swatch light"></i>Light mud</span>
        <span><i class="legend-swatch gas"></i>Gas</span>
        <span><i class="legend-swatch heavy"></i>Heavy mud</span>
      </div>

      <div class="annulus-column">
        <div
          v-if="showConductorCasing"
          class="surface-formation"
          :style="surfaceFormationStyle"
          aria-hidden="true"
        ></div>
        <div
          v-if="showConductorCasing"
          class="conductor-depth-formation"
          :style="conductorDepthFormationStyle"
          aria-hidden="true"
        ></div>
        <div class="exposed-formation" aria-hidden="true"></div>

        <div
          v-if="showConductorCasing"
          class="conductor-casing conductor-casing-left"
          :style="conductorCasingStyle"
          aria-hidden="true"
        >
          <span class="conductor-shoe">
            <i class="shoe-wing shoe-wing-out-left"></i>
          </span>
        </div>
        <div
          v-if="showConductorCasing"
          class="conductor-casing conductor-casing-right"
          :style="conductorCasingStyle"
          aria-hidden="true"
        >
          <span class="conductor-shoe">
            <i class="shoe-wing shoe-wing-out-right"></i>
          </span>
        </div>

        <div
          v-for="cell in annulusCells"
          :key="cell.index"
          class="annulus-cell"
          :style="cell.style"
          :title="cell.label"
        >
          <span class="cell-fill gas-fill" :style="cell.gasStyle"></span>
          <span class="cell-fill liquid-fill" :style="cell.liquidStyle"></span>
        </div>

        <div class="inner-column" aria-hidden="true">
          <div
            v-for="cell in drillpipeCells"
            :key="`inner-${cell.index}`"
            class="inner-cell"
            :style="cell.style"
          >
            <span class="cell-fill gas-fill" :style="cell.gasStyle"></span>
            <span class="cell-fill liquid-fill" :style="cell.liquidStyle"></span>
          </div>
        </div>

        <div class="drill-bit" aria-hidden="true"></div>
      </div>
    </section>

    <section class="gauges-panel card">
      <div class="gauges-heading">
        <div>
          <h2>Pressures</h2>
        </div>
        <span class="gauges-unit">atm</span>
      </div>
      <PressureGauge
        v-for="gauge in gauges"
        :key="gauge.id"
        :config="gauge"
        :value="gaugeValuesById[gauge.id]"
      />
    </section>

    <section class="pressure-chart-panel card">
      <div class="chart-header">
        <h2>Pzab Trend</h2>
        <strong>{{ bottomholePressure }} atm</strong>
      </div>
      <svg viewBox="0 0 460 112" class="pressure-chart" role="img" aria-label="Bottomhole pressure trend">
        <line x1="28" y1="14" x2="28" y2="92" class="chart-axis" />
        <line x1="28" y1="92" x2="442" y2="92" class="chart-axis" />
        <line
          v-for="line in pzabChartGrid"
          :key="line.y"
          x1="28"
          :y1="line.y"
          x2="442"
          :y2="line.y"
          class="chart-grid"
        />
        <polyline v-if="pzabChartPoints" :points="pzabChartPoints" class="chart-line" />
        <circle
          v-if="pzabChartLastPoint"
          :cx="pzabChartLastPoint.x"
          :cy="pzabChartLastPoint.y"
          r="4"
          class="chart-dot"
        />
      </svg>
    </section>
    </div>
  </main>
</template>

<script lang="ts">
import PressureGauge from './components/PressureGauge.vue'
import gaugeConfig from './config/pressure-gauge.json'

const CHOKE_MAX_ANGLE = 60
const CHOKE_GAUGE_TICKS = [0, 25, 50, 75, 100]
const CHOKE_SPEED_OPTIONS = [5, 4, 3, 2, 1]
const DEFAULT_CHOKE_SPEED_OPTION = CHOKE_SPEED_OPTIONS[Math.floor(CHOKE_SPEED_OPTIONS.length / 2)] ?? 3
const PASCAL_PER_ATM = 101325
type RunState = 'active' | 'paused' | 'failed' | 'fast_forward' | 'completed'

type RunPageData = {
  runId?: number
  caseId?: number
  user?: string
  sessionId?: string
  runState?: RunState
  resultMessage?: string
  analysisUrl?: string
  caseData?: Record<string, unknown>
  frontendInitData?: {
    casing_p?: number
    drillpipe_p?: number
    Ppl?: number
    pzab?: number
    heavy_mud_pos?: number
    pump_speed_init?: number
    total_strokes?: number
    choke_speed?: number
    choke_regulator_1?: number
    choke_regulator_2?: number
    choke_position_init?: number
    mud_switch?: number
    pzab_history?: number[]
    annulus_content?: Array<[number, number, number]>
    drillpipe_content?: Array<[number, number, number]>
  }
}

type PressureResponse = {
  frontend_init_data?: RunPageData['frontendInitData']
  run_state?: RunState
  failure_message?: string
  result_message?: string
  analysis_url?: string
} & Record<string, unknown>

declare global {
  interface Window {
    runPageData?: RunPageData
  }
}

export default {
  components: {
    PressureGauge,
  },
  data() {
    return {
      pageData: window.runPageData || {},
      pollUrl: '',
      pollIntervalMs: 1000,
      chokeTickIntervalMs: 250,
      gaugeConfig,
      pollId: null as ReturnType<typeof setInterval> | null,
      chokeTickId: null as ReturnType<typeof setInterval> | null,
      socket: null as WebSocket | null,
      pumpSpeed: 0,
      mudSwitch: 0,
      chokeAngle: 0,
      chokeSpeed: 0,
      baseChokeSpeed: 0,
      chokeRegulator1: 1,
      chokeRegulator2: 1,
      chokePositionValue: 0,
      selectedChokeSpeed: DEFAULT_CHOKE_SPEED_OPTION,
      runState: (window.runPageData?.runState || 'active') as RunState,
      stateBeforePause: 'active' as RunState,
      resultMessage: window.runPageData?.resultMessage || '',
      analysisUrl: window.runPageData?.analysisUrl || '',
    }
  },
  computed: {
    gauges() {
      if (!Array.isArray(this.gaugeConfig.gauges)) return []
      return this.gaugeConfig.gauges.map((gauge) => ({
        ...gauge,
        unit: 'atm',
        maxPressure: 300,
        tickValues: [0, 50, 100, 150, 200, 250, 300],
      }))
    },
    gaugeValuesById() {
      const nextValues: Record<string, number> = {}
      if (typeof this.frontendInitData.drillpipe_p === 'number') {
        nextValues['pressure-1'] = this.toAtm(this.frontendInitData.drillpipe_p)
      }
      if (typeof this.frontendInitData.casing_p === 'number') {
        nextValues['pressure-2'] = this.toAtm(this.frontendInitData.casing_p)
      }
      return nextValues
    },
    frontendInitData() {
      return this.pageData.frontendInitData || {}
    },
    casingPressure() {
      const value = this.frontendInitData.casing_p
      return typeof value === 'number' ? this.toAtm(value).toFixed(2) : '-'
    },
    drillpipePressure() {
      const value = this.frontendInitData.drillpipe_p
      return typeof value === 'number' ? this.toAtm(value).toFixed(2) : '-'
    },
    formationPressure() {
      const value = this.frontendInitData.Ppl
      return typeof value === 'number' ? this.toAtm(value).toFixed(2) : '-'
    },
    bottomholePressure() {
      const value = this.frontendInitData.pzab
      return typeof value === 'number' ? this.toAtm(value).toFixed(2) : '-'
    },
    pzabHistory() {
      const values = this.frontendInitData.pzab_history
      if (!Array.isArray(values)) return []
      return values
        .filter((value) => typeof value === 'number' && Number.isFinite(value))
        .map((value) => this.toAtm(value))
    },
    pzabChartGrid() {
      return [14, 33.5, 53, 72.5, 92].map((y) => ({ y }))
    },
    pzabChartLastPoint() {
      const points = this.pzabChartPointList
      return points.length ? points[points.length - 1] : null
    },
    pzabChartPointList() {
      const values = this.pzabHistory
      if (!values.length) return []

      const min = Math.min(...values)
      const max = Math.max(...values)
      const span = Math.max(max - min, 0.1)
      const left = 28
      const top = 14
      const width = 414
      const height = 78
      const xStep = values.length > 1 ? width / (values.length - 1) : 0

      return values.map((value, index) => ({
        x: left + index * xStep,
        y: top + (1 - (value - min) / span) * height,
      }))
    },
    pzabChartPoints() {
      return this.pzabChartPointList
        .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
        .join(' ')
    },
    reversedAnnulusContent() {
      const content = this.frontendInitData.annulus_content
      if (!Array.isArray(content)) return []
      return [...content].reverse()
    },
    conductorDepthFraction() {
      const depth = Number(this.pageData.caseData?.conductor_depth ?? 400)
      const wellLength = Number(this.pageData.caseData?.well_l ?? 0)
      if (!Number.isFinite(depth) || !Number.isFinite(wellLength) || wellLength <= 0) {
        return 0
      }
      return Math.min(Math.max(depth / wellLength, 0), 1)
    },
    showConductorCasing() {
      return this.conductorDepthFraction > 0
    },
    conductorCasingStyle() {
      return {
        height: `calc((100% - 16px - var(--formation-height) + var(--well-drop)) * ${this.conductorDepthFraction})`,
      }
    },
    surfaceFormationStyle() {
      return {
        height: `calc((100% - 16px - var(--formation-height)) * ${this.conductorDepthFraction})`,
      }
    },
    conductorDepthFormationStyle() {
      return {
        top: `calc(8px + (100% - 16px - var(--formation-height)) * ${this.conductorDepthFraction})`,
        height: '5%',
      }
    },
    backendTotalStrokes() {
      const value = this.frontendInitData.total_strokes
      return typeof value === 'number' && Number.isFinite(value) ? value : 0
    },
    totalStrokes() {
      return this.backendTotalStrokes
    },
    formattedTotalStrokes() {
      return Math.round(this.totalStrokes).toString()
    },
    currentCaseId() {
      const value = this.pageData.caseId
      return typeof value === 'number' && Number.isFinite(value) ? value : null
    },
    currentRunId() {
      const value = this.pageData.runId
      return typeof value === 'number' && Number.isFinite(value) ? value : null
    },
    isPaused() {
      return this.runState === 'paused'
    },
    isFastForward() {
      return this.runState === 'fast_forward'
    },
    stateControlsLocked() {
      return this.runState === 'failed' || this.runState === 'completed'
    },
    runStateLabel() {
      return {
        active: 'Active',
        paused: 'Paused',
        failed: 'Failed',
        fast_forward: 'Fast forward',
        completed: 'Finished',
      }[this.runState] || 'Active'
    },
    terminalMessage() {
      if (this.resultMessage) return this.resultMessage
      return this.runState === 'completed' ? 'The case has been finished.' : ''
    },
    chokePositionPercent() {
      return Math.round(this.chokePositionValue)
    },
    chokeSpeedOptions() {
      return CHOKE_SPEED_OPTIONS
    },
    chokeHandleStyle() {
      return {
        transform: `translateX(-50%) rotate(${this.chokeAngle}deg)`,
      }
    },
    chokeGaugeTicks() {
      const cx = 110
      const cy = 122
      const outer = 82
      const inner = 68
      const labelRadius = 56

      return CHOKE_GAUGE_TICKS.map((value) => {
        const ratio = value / 100
        const angle = Math.PI - ratio * Math.PI

        return {
          value,
          x1: cx + outer * Math.cos(angle),
          y1: cy - outer * Math.sin(angle),
          x2: cx + inner * Math.cos(angle),
          y2: cy - inner * Math.sin(angle),
          lx: cx + labelRadius * Math.cos(angle),
          ly: cy - labelRadius * Math.sin(angle) + 4,
        }
      })
    },
    chokeNeedle() {
      const ratio = this.chokePositionPercent / 100
      const angle = Math.PI - ratio * Math.PI
      const radius = 62

      return {
        x: 110 + radius * Math.cos(angle),
        y: 122 - radius * Math.sin(angle),
      }
    },
    annulusCells() {
      return this.reversedAnnulusContent.map((row, index) => {
        const rawHeightFraction = Number(row?.[0] ?? 0)
        const heightFraction = Number.isFinite(rawHeightFraction)
          ? Math.min(Math.max(rawHeightFraction, 0), 1)
          : 0
        const liquidTone = Number(row?.[1] ?? 0) === 1 ? 1 : 0
        const rawGasFraction = Number(row?.[2] ?? 0)
        const gasFraction = Number.isFinite(rawGasFraction)
          ? Math.min(Math.max(rawGasFraction, 0), 1)
          : 0
        const gasPercent = gasFraction * 100
        const liquidPercent = 100 - gasPercent
        const liquidColor = liquidTone === 1 ? '#234e8c' : '#5ab8cf'
        const gasColor = '#d69a24'

        return {
          index,
          label: `Cell ${index}: height=${heightFraction.toFixed(4)}, tone=${liquidTone}, gas=${gasFraction.toFixed(4)}`,
          style: {
            flexBasis: `${heightFraction * 100}%`,
          },
          gasStyle: {
            flexBasis: `${gasPercent}%`,
            background: gasColor,
          },
          liquidStyle: {
            flexBasis: `${liquidPercent}%`,
            background: liquidColor,
          },
        }
      })
    },
    drillpipeCells() {
      const content = this.frontendInitData.drillpipe_content
      if (!Array.isArray(content)) return []

      return [...content].reverse().map((row, index) => {
        const rawHeightFraction = Number(row?.[0] ?? 0)
        const heightFraction = Number.isFinite(rawHeightFraction)
          ? Math.min(Math.max(rawHeightFraction, 0), 1)
          : 0
        const liquidTone = Number(row?.[1] ?? 0) === 1 ? 1 : 0
        const liquidColor = liquidTone === 1 ? '#234e8c' : '#5ab8cf'

        return {
          index,
          style: {
            flexBasis: `${heightFraction * 100}%`,
          },
          gasStyle: {
            display: 'none',
          },
          liquidStyle: {
            flexBasis: '100%',
            background: liquidColor,
          },
        }
      })
    },
  },
  mounted() {
    window.addEventListener('mouseup', this.resetChoke)
    if (typeof this.currentRunId === 'number') {
      this.pollUrl = this.getApiUrl(`/number/${this.currentRunId}`)
      this.socket = new WebSocket(this.getSocketUrl(`/ws/number/${this.currentRunId}`))
      this.socket.addEventListener('message', (event) => {
        const payload = JSON.parse(event.data) as PressureResponse
        this.applyPressurePayload(payload)
      })
      this.socket.addEventListener('error', () => {
        this.socket = null
      })
      this.socket.addEventListener('close', () => {
        this.socket = null
      })
    }
    if (typeof this.frontendInitData.pump_speed_init === 'number') {
      this.pumpSpeed = Math.max(0, this.frontendInitData.pump_speed_init)
    }
    if (typeof this.frontendInitData.mud_switch === 'number') {
      this.mudSwitch = this.frontendInitData.mud_switch === 1 ? 1 : 0
    }
    if (typeof this.frontendInitData.choke_speed === 'number') {
      this.baseChokeSpeed = Math.max(0, this.frontendInitData.choke_speed)
    }
    if (typeof this.frontendInitData.choke_regulator_1 === 'number') {
      this.chokeRegulator1 = Math.max(1, this.frontendInitData.choke_regulator_1)
    }
    if (typeof this.frontendInitData.choke_regulator_2 === 'number') {
      this.chokeRegulator2 = Math.max(1, this.frontendInitData.choke_regulator_2)
    }
    if (typeof this.frontendInitData.choke_position_init === 'number') {
      this.chokePositionValue = Math.min(100, Math.max(0, this.frontendInitData.choke_position_init))
    }
    this.updateChokeSpeed()
    window.addEventListener('pagehide', this.stopPolling)
    window.addEventListener('beforeunload', this.stopPolling)
    this.pollId = setInterval(() => this.fetchValues(), this.pollIntervalMs)
    this.chokeTickId = setInterval(() => this.tickChokePosition(), this.chokeTickIntervalMs)
  },
  watch: {
    selectedChokeSpeed() {
      this.updateChokeSpeed()
    },
  },
  beforeDestroy() {
    window.removeEventListener('mouseup', this.resetChoke)
    window.removeEventListener('pagehide', this.stopPolling)
    window.removeEventListener('beforeunload', this.stopPolling)
    this.stopPolling()
  },
  beforeUnmount() {
    window.removeEventListener('mouseup', this.resetChoke)
    window.removeEventListener('pagehide', this.stopPolling)
    window.removeEventListener('beforeunload', this.stopPolling)
    this.stopPolling()
  },
  methods: {
    stopPolling() {
      if (this.pollId) {
        clearInterval(this.pollId)
        this.pollId = null
      }
      if (this.chokeTickId) {
        clearInterval(this.chokeTickId)
        this.chokeTickId = null
      }
      if (this.socket) {
        this.socket.close()
        this.socket = null
      }
    },
    increasePumpSpeed() {
      this.pumpSpeed += 5
    },
    decreasePumpSpeed() {
      this.pumpSpeed = Math.max(0, this.pumpSpeed - 5)
    },
    toggleMudSwitch() {
      this.mudSwitch = this.mudSwitch === 1 ? 0 : 1
    },
    async setRunState(nextState: RunState) {
      if (typeof this.currentRunId !== 'number') return
      try {
        const response = await fetch(this.getApiUrl(`/runs/${this.currentRunId}/state`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state: nextState }),
        })
        if (!response.ok) return
        const payload = (await response.json()) as PressureResponse
        if (payload.run_state) this.runState = payload.run_state
        if (payload.result_message) this.resultMessage = payload.result_message
        if (payload.analysis_url) this.analysisUrl = payload.analysis_url
        if (payload.run_state === 'completed') this.stopPolling()
      } catch {
        // Preserve the last confirmed server state when the request fails.
      }
    },
    togglePause() {
      if (this.isPaused) {
        const resumeState = this.stateBeforePause === 'fast_forward' ? 'fast_forward' : 'active'
        void this.setRunState(resumeState)
        return
      }
      this.stateBeforePause = this.runState
      void this.setRunState('paused')
    },
    toggleFastForward() {
      if (this.isPaused || this.stateControlsLocked) return
      void this.setRunState(this.isFastForward ? 'active' : 'fast_forward')
    },
    finishRun() {
      if (this.stateControlsLocked) return
      void this.setRunState('completed')
    },
    toAtm(value: number) {
      return value / PASCAL_PER_ATM
    },
    updateChokeSpeed() {
      const defaultPosition = DEFAULT_CHOKE_SPEED_OPTION
      const offset = Number(this.selectedChokeSpeed) - defaultPosition
      if (!offset) {
        this.chokeSpeed = this.baseChokeSpeed
        return
      }

      const factor = Math.abs(offset) === 1 ? this.chokeRegulator1 : this.chokeRegulator2
      this.chokeSpeed = offset > 0
        ? this.baseChokeSpeed * factor
        : this.baseChokeSpeed / factor
    },
    setChokeDirection(direction: 'left' | 'right') {
      this.chokeAngle = direction === 'left' ? -CHOKE_MAX_ANGLE : CHOKE_MAX_ANGLE
    },
    resetChoke() {
      this.chokeAngle = 0
    },
    tickChokePosition() {
      if (this.chokeAngle === CHOKE_MAX_ANGLE && this.chokeSpeed > 0) {
        this.chokePositionValue = Math.min(100, this.chokePositionValue + this.chokeSpeed)
      } else if (this.chokeAngle === -CHOKE_MAX_ANGLE && this.chokeSpeed > 0) {
        this.chokePositionValue = Math.max(0, this.chokePositionValue - this.chokeSpeed)
      }
    },
    getApiUrl(path: string) {
      const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
      if (isLocalhost && window.location.port !== '8001') {
        return `http://127.0.0.1:8001${path}`
      }
      return path
    },
    getSocketUrl(path: string) {
      const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
      if (isLocalhost && window.location.port !== '8001') {
        return `ws://127.0.0.1:8001${path}`
      }
      const socketProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${socketProtocol}//${window.location.host}${path}`
    },
    applyPressurePayload(payload: PressureResponse) {
      if (payload.run_state) this.runState = payload.run_state
      if (payload.failure_message) this.resultMessage = payload.failure_message
      if (payload.analysis_url) this.analysisUrl = payload.analysis_url
      if (payload.frontend_init_data && typeof payload.frontend_init_data === 'object') {
        this.pageData = {
          ...this.pageData,
          frontendInitData: {
            ...this.pageData.frontendInitData,
            ...payload.frontend_init_data,
          },
        }

        if (typeof payload.frontend_init_data.choke_speed === 'number') {
          this.baseChokeSpeed = Math.max(0, payload.frontend_init_data.choke_speed)
        }
        if (typeof payload.frontend_init_data.choke_regulator_1 === 'number') {
          this.chokeRegulator1 = Math.max(1, payload.frontend_init_data.choke_regulator_1)
        }
        if (typeof payload.frontend_init_data.choke_regulator_2 === 'number') {
          this.chokeRegulator2 = Math.max(1, payload.frontend_init_data.choke_regulator_2)
        }
        if (typeof payload.frontend_init_data.mud_switch === 'number') {
          this.mudSwitch = payload.frontend_init_data.mud_switch === 1 ? 1 : 0
        }
        this.updateChokeSpeed()
      }
    },
    async fetchValues() {
      try {
        if (!this.pollUrl) return
        const requestPayload = {
          choke_position: this.chokePositionValue,
          pump_speed: this.pumpSpeed,
          mud_switch: this.mudSwitch,
        }
        if (this.socket?.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify(requestPayload))
          return
        }
        const response = await fetch(this.pollUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestPayload),
        })
        if (!response.ok) return

        const payload = (await response.json()) as PressureResponse
        this.applyPressurePayload(payload)
      } catch {
        // Keep last values if polling fails.
      }
    },
  },
}
</script>

<style scoped>
.page {
  --api-bg: #111821;
  --api-panel: #202832;
  --api-panel-dark: #161d25;
  --api-panel-soft: #27313d;
  --api-border: #65717c;
  --api-border-dark: #090d12;
  --api-text: #edf2f4;
  --api-muted: #aeb9c2;
  --api-yellow: #d69a24;
  --api-red: #b63b30;
  --api-green: #3f8f5f;
  --api-cyan: #5ab8cf;
  --api-blue: #234e8c;
  min-height: 100vh;
  display: grid;
  gap: 10px;
  padding: 12px;
  justify-content: start;
  align-content: start;
  grid-template-columns: 244px 506px 506px;
  grid-template-rows: auto;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.026) 1px, transparent 1px),
    linear-gradient(180deg, #2a333d 0%, var(--api-bg) 100%);
  background-size: 24px 24px, 24px 24px, auto;
  color: var(--api-text);
  font-family: 'Segoe UI', Tahoma, sans-serif;
}

.pump-metrics {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}

.pump-metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(174, 185, 194, 0.22);
  border-radius: 6px;
  background: linear-gradient(180deg, #2a3440, #182029);
  color: var(--api-text);
}

.pump-label {
  font-size: 0.92rem;
}

.pump-controls {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
}

.pump-regulator {
  padding: 0 8px;
  font-size: 0.85rem;
  color: var(--api-muted);
  white-space: nowrap;
}

.pump-button {
  min-height: 34px;
  border: 1px solid #75808a;
  border-radius: 6px;
  background: linear-gradient(180deg, #4b5662, #222b34);
  color: var(--api-text);
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 2px 0 var(--api-border-dark);
}

.pump-button:hover {
  background: linear-gradient(180deg, #596672, #2a3440);
}

.mud-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  margin-top: 8px;
  min-height: 36px;
  padding: 6px 8px;
  border: 1px solid rgba(174, 185, 194, 0.32);
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), transparent 42%),
    linear-gradient(180deg, #2a3440, #151d25);
  color: var(--api-text);
  font-weight: 700;
  cursor: pointer;
  box-shadow:
    inset 0 0 0 1px rgba(0, 0, 0, 0.42),
    0 2px 0 var(--api-border-dark);
}

.mud-switch-track {
  position: relative;
  flex: 0 0 auto;
  width: 54px;
  height: 24px;
  border: 1px solid #7b8792;
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(90, 184, 207, 0.55), rgba(90, 184, 207, 0.12)),
    #0e151c;
  box-shadow:
    inset 0 2px 5px rgba(0, 0, 0, 0.62),
    inset 0 0 0 1px rgba(255, 255, 255, 0.05);
}

.mud-switch-track i {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 22px;
  height: 18px;
  border: 1px solid #c7cdd1;
  border-radius: 3px;
  background: linear-gradient(180deg, #edf2f4, #848e96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.45),
    0 2px 4px rgba(0, 0, 0, 0.45);
  transition: transform 160ms ease;
}

.mud-switch.heavy {
  border-color: rgba(214, 154, 36, 0.56);
  background:
    linear-gradient(180deg, rgba(214, 154, 36, 0.15), transparent 44%),
    linear-gradient(180deg, #30333a, #181d24);
}

.mud-switch.heavy .mud-switch-track {
  background:
    linear-gradient(90deg, rgba(35, 78, 140, 0.16), rgba(214, 154, 36, 0.72)),
    #0e151c;
}

.mud-switch.heavy .mud-switch-track i {
  transform: translateX(28px);
}

.gauges-panel {
  display: grid;
  grid-column: 3;
  grid-row: 1;
  gap: 10px;
  grid-template-columns: repeat(2, 244px);
  align-items: start;
  justify-content: start;
}

.pressure-chart-panel {
  grid-column: 3;
  grid-row: 2;
  box-sizing: border-box;
  width: 506px;
  padding: 10px;
  border: 3px solid var(--api-border);
  border-radius: 6px;
  background: linear-gradient(180deg, var(--api-panel), var(--api-panel-dark));
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.06),
    inset 0 0 0 4px rgba(0, 0, 0, 0.22),
    0 18px 36px rgba(0, 0, 0, 0.32);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 6px;
}

.chart-header h2 {
  margin: 0;
  color: var(--api-yellow);
  font-size: 0.9rem;
  text-transform: uppercase;
}

.chart-header strong {
  color: var(--api-text);
  font-size: 0.95rem;
}

.pressure-chart {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid rgba(174, 185, 194, 0.18);
  border-radius: 4px;
  background: radial-gradient(circle at center, #202a34 0%, #10161d 100%);
}

.chart-axis {
  stroke: rgba(200, 208, 214, 0.58);
  stroke-width: 1.5;
}

.chart-grid {
  stroke: rgba(200, 208, 214, 0.12);
  stroke-width: 1;
}

.chart-line {
  fill: none;
  stroke: var(--api-yellow);
  stroke-width: 3;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.chart-dot {
  fill: #e5473d;
  stroke: #edf2f4;
  stroke-width: 1.5;
}

.annulus-panel {
  grid-column: 1;
  grid-row: 1;
  justify-self: start;
  align-self: start;
  width: 100%;
  max-width: 244px;
  box-sizing: border-box;
  padding: 12px;
  border-radius: 6px;
  background: linear-gradient(180deg, var(--api-panel), var(--api-panel-dark));
  border: 3px solid var(--api-border);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.06),
    inset 0 0 0 4px rgba(0, 0, 0, 0.22),
    0 18px 36px rgba(0, 0, 0, 0.32);
}

.choke-panel {
  grid-column: 2;
  grid-row: 1;
  box-sizing: border-box;
  width: 100%;
  max-width: 506px;
  padding: 12px;
  border-radius: 6px;
  border: 3px solid var(--api-border);
  background: linear-gradient(180deg, var(--api-panel), var(--api-panel-dark));
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.06),
    inset 0 0 0 4px rgba(0, 0, 0, 0.22),
    0 18px 36px rgba(0, 0, 0, 0.32);
}

.pump-inline-panel {
  margin-top: 4px;
  padding: 10px;
  border: 1px solid rgba(174, 185, 194, 0.2);
  border-radius: 6px;
  background: linear-gradient(180deg, #252f39, #171f27);
}

.choke-indicator {
  margin-bottom: 10px;
  padding: 8px 8px calc(8px + var(--formation-height));
  border: 1px solid rgba(174, 185, 194, 0.2);
  border-radius: 6px;
  background: linear-gradient(180deg, #252f39, #171f27);
  box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.25);
}

.choke-indicator-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 8px;
  align-items: end;
  margin-bottom: 5px;
}

.choke-indicator-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 8px;
  align-items: stretch;
}

.choke-indicator-title {
  text-align: center;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--api-yellow);
  letter-spacing: 0;
  text-transform: uppercase;
}

.choke-speed-heading {
  text-align: center;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--api-muted);
  text-transform: uppercase;
}

.choke-gauge-shell {
  display: grid;
  align-items: center;
  overflow: hidden;
  min-height: 100%;
  padding: 3px 6px 0;
  border: 1px solid rgba(174, 185, 194, 0.18);
  border-radius: 6px;
  background: radial-gradient(circle at center, #202a34 0%, #10161d 100%);
}

.choke-gauge {
  display: block;
  width: 100%;
  margin: 0 auto;
  height: auto;
  max-height: 132px;
  transform: scale(1.22);
  transform-origin: 50% 58%;
}

.choke-speed-panel {
  display: grid;
  grid-template-rows: auto repeat(5, minmax(0, 1fr)) auto;
  align-items: center;
  margin: 0;
  padding: 6px;
  border: 1px solid rgba(174, 185, 194, 0.18);
  border-radius: 6px;
  background: #151d25;
}

.choke-speed-hint {
  display: block;
  text-align: center;
  font-size: 0.72rem;
  color: var(--api-muted);
}

.choke-speed-hint.top {
  margin-bottom: 3px;
}

.choke-speed-hint.bottom {
  margin-top: 3px;
}

.choke-speed-option {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 20px;
  margin: 0;
  font-size: 0.84rem;
  color: var(--api-text);
  cursor: pointer;
}

.choke-speed-option input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.choke-speed-detent {
  display: block;
  width: 48px;
  height: 14px;
  border: 1px solid #6f7a84;
  border-radius: 3px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 50%),
    #0e151c;
  box-shadow:
    inset 0 1px 3px rgba(0, 0, 0, 0.68),
    0 1px 0 rgba(255, 255, 255, 0.08);
}

.choke-speed-option input:checked + .choke-speed-detent {
  border-color: rgba(214, 154, 36, 0.85);
  background:
    linear-gradient(180deg, #f0b640, #a66c18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 0 10px rgba(214, 154, 36, 0.38);
}

.choke-speed-option input:focus-visible + .choke-speed-detent,
.mud-switch:focus-visible {
  outline: 2px solid var(--api-yellow);
  outline-offset: 2px;
}

.choke-gauge-arc {
  fill: none;
  stroke: var(--api-yellow);
  stroke-width: 5;
  stroke-linecap: round;
}

.choke-gauge-tick {
  stroke: #c8d0d6;
  stroke-width: 2;
}

.choke-gauge-label {
  font-size: 10px;
  font-weight: 600;
  fill: #c8d0d6;
}

.choke-gauge-needle {
  stroke: #e5473d;
  stroke-width: 3;
  stroke-linecap: round;
}

.choke-gauge-center {
  fill: #e5473d;
}

.choke-gauge-value {
  font-size: 15px;
  font-weight: 700;
  fill: var(--api-yellow);
}

.choke-visual {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: end;
  height: 178px;
  margin-bottom: 10px;
  border: 1px solid rgba(174, 185, 194, 0.2);
  border-radius: 6px;
  background:
    linear-gradient(90deg, rgba(182, 59, 48, 0.24), transparent 48%, transparent 52%, rgba(63, 143, 95, 0.24)),
    linear-gradient(180deg, #252f39, #141b23);
}

.choke-hit-area {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 50%;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  z-index: 2;
}

.choke-hit-area.left {
  left: 0;
  background: linear-gradient(90deg, rgba(182, 59, 48, 0.26), rgba(182, 59, 48, 0.06));
}

.choke-hit-area.right {
  right: 0;
  background: linear-gradient(270deg, rgba(63, 143, 95, 0.26), rgba(63, 143, 95, 0.06));
}

.choke-hit-area:hover {
  filter: brightness(1.04);
}

.choke-zone-label {
  position: absolute;
  top: 50%;
  z-index: 0;
  transform: translateY(-50%);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--api-text);
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
  pointer-events: none;
  width: 50%;
  text-align: center;
}

.choke-zone-label.close {
  left: 0;
  color: #ff6a5e;
}

.choke-zone-label.open {
  right: 0;
  color: #70d596;
}

.choke-slot {
  position: absolute;
  bottom: 24px;
  z-index: 1;
  pointer-events: none;
  width: 210px;
  height: 12px;
  border-radius: 999px;
  background: #0c1117;
  box-shadow: inset 0 0 0 1px rgba(200, 208, 214, 0.22);
}

.choke-handle {
  position: absolute;
  bottom: 30px;
  left: 50%;
  z-index: 3;
  pointer-events: none;
  width: 12px;
  height: 112px;
  transform-origin: bottom center;
  border-radius: 999px;
  background: linear-gradient(180deg, #d5d8da, #6d767e 45%, #232b34);
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.42);
}

.choke-knob {
  position: absolute;
  top: -12px;
  left: 50%;
  pointer-events: none;
  width: 30px;
  height: 30px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #f0f2f3, #6e7881 55%, #252d35 100%);
  box-shadow:
    inset 0 0 0 2px rgba(255, 255, 255, 0.24),
    0 4px 10px rgba(0, 0, 0, 0.5);
}

.annulus-header h2 {
  margin: 0 0 5px;
  color: var(--api-yellow);
  text-transform: uppercase;
}

.pressure-summary {
  display: grid;
  gap: 4px;
  margin: 0 0 10px;
  color: var(--api-muted);
}

.pressure-summary span {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 0;
  border-bottom: 1px solid rgba(174, 185, 194, 0.12);
}

.pressure-summary b {
  color: var(--api-text);
}

.annulus-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 0.82rem;
  color: var(--api-muted);
}

.annulus-legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.legend-swatch {
  width: 14px;
  height: 14px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 2px;
  display: inline-block;
}

.legend-swatch.light {
  background: var(--api-cyan);
}

.legend-swatch.gas {
  background: var(--api-yellow);
}

.legend-swatch.heavy {
  background: var(--api-blue);
}

.annulus-column {
  --well-width: 33.5%;
  --pipe-width: 12.46%;
  --formation-height: 42px;
  --formation-rock: #77624c;
  --formation-accent: #b9653f;
  --formation-gas-base: #30271e;
  --formation-gas-line: rgba(224, 161, 38, 0.78);
  --well-drop: 21px;
  --well-shift: 0px;
  --well-center: calc(50% - var(--well-shift));
  --well-edge-left: calc((100% - var(--well-width)) / 2 - var(--well-shift));
  --well-edge-right: calc((100% - var(--well-width)) / 2 + var(--well-shift));
  box-sizing: border-box;
  position: relative;
  display: flex;
  flex-direction: column-reverse;
  align-items: flex-start;
  height: 420px;
  gap: 0;
  padding: 8px 8px calc(var(--formation-height) - var(--well-drop));
  border: 3px solid #747f88;
  border-radius: 0;
  background: #2f3437;
  background-clip: padding-box;
  box-shadow: none;
}

.annulus-column::before,
.annulus-column::after {
  content: '';
  position: absolute;
  top: 8px;
  bottom: calc(var(--formation-height) - var(--well-drop));
  z-index: 3;
  width: 3px;
  background: #747f88;
  pointer-events: none;
}

.annulus-column::before {
  left: var(--well-edge-left);
}

.annulus-column::after {
  right: var(--well-edge-right);
}

.surface-formation {
  position: absolute;
  top: 8px;
  left: 0;
  right: 0;
  z-index: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(255, 255, 255, 0.035), transparent),
    var(--formation-rock);
}

.conductor-depth-formation {
  position: absolute;
  left: 0;
  right: 0;
  z-index: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(48, 39, 30, 0.24), transparent 38%, rgba(48, 39, 30, 0.18)),
    var(--formation-accent);
  box-shadow:
    inset 0 1px rgba(255, 220, 184, 0.18),
    inset 0 -1px rgba(48, 39, 30, 0.28);
}

.exposed-formation {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;
  height: var(--formation-height);
  pointer-events: none;
  border: 0;
  background-color: var(--formation-gas-base);
  background-image:
    repeating-linear-gradient(
      45deg,
      transparent 0 5px,
      var(--formation-gas-line) 5px 6px,
      transparent 6px 10px
    ),
    repeating-linear-gradient(
      -45deg,
      transparent 0 5px,
      var(--formation-gas-line) 5px 6px,
      transparent 6px 10px
    );
  box-shadow: inset 0 1px rgba(224, 161, 38, 0.42);
}

.annulus-cell {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column-reverse;
  flex: 0 0 auto;
  width: var(--well-width);
  margin-left: var(--well-edge-left);
  min-height: 0;
  overflow: hidden;
}

.conductor-casing {
  position: absolute;
  top: 8px;
  z-index: 6;
  width: 6px;
  min-height: 14px;
  pointer-events: none;
  border-radius: 0;
  background: #3e454c;
  box-shadow: none;
}

.conductor-casing-left {
  left: calc(var(--well-edge-left) - 6px);
}

.conductor-casing-right {
  right: calc(var(--well-edge-right) - 6px);
}

.conductor-shoe {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 0;
}

.shoe-wing {
  position: absolute;
  bottom: 0;
  width: 0;
  height: 0;
  border-top: 10px solid transparent;
}

.shoe-wing-out-left {
  left: -18px;
  border-right: 18px solid #3e454c;
}

.shoe-wing-out-right {
  left: 6px;
  border-left: 18px solid #3e454c;
}

.cell-fill {
  display: block;
  flex: 0 0 auto;
  width: 100%;
  min-height: 0;
}

.inner-column {
  box-sizing: border-box;
  position: absolute;
  z-index: 5;
  top: 12px;
  bottom: calc(var(--formation-height) - var(--well-drop) + 26px);
  left: var(--well-center);
  width: var(--pipe-width);
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 0;
  pointer-events: none;
  padding: 0;
  overflow: hidden;
  border-radius: 0;
  border: 2px solid #000;
  background: #5ab8cf;
  box-shadow: none;
}

.inner-cell {
  display: flex;
  flex-direction: column-reverse;
  flex: 0 0 auto;
  min-height: 0;
  overflow: hidden;
}

.drill-bit {
  position: absolute;
  left: var(--well-center);
  bottom: calc(var(--formation-height) - var(--well-drop) + 2px);
  z-index: 8;
  width: calc(var(--well-width) * 0.792);
  height: 26px;
  transform: translateX(-50%);
  pointer-events: none;
  background: #111;
  clip-path: polygon(
    8% 0,
    92% 0,
    100% 18%,
    100% 76%,
    91% 100%,
    82% 76%,
    73% 100%,
    64% 76%,
    55% 100%,
    46% 76%,
    37% 100%,
    28% 76%,
    19% 100%,
    10% 76%,
    0 100%,
    0 18%
  );
}

.drill-bit::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 5px;
  transform: translateX(-50%);
  background: #5ab8cf;
}

@media (max-width: 900px) {
  .page {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .pump-panel,
  .gauges-panel,
  .pressure-chart-panel,
  .annulus-panel,
  .choke-panel {
    grid-column: auto;
    grid-row: auto;
  }

  .pressure-chart-panel {
    width: 100%;
  }
}

/* Bootstrap-based dashboard layer */
:global(*) {
  box-sizing: border-box;
}

:global(html) {
  background: #0b1118;
}

:global(body) {
  min-width: 320px;
  margin: 0;
  background: #0b1118;
}

:global(button),
:global(input) {
  font: inherit;
}

.page {
  --api-bg: #0b1118;
  --api-panel: #151d27;
  --api-panel-dark: #101720;
  --api-panel-soft: #1b2531;
  --api-border: #2b3948;
  --api-border-dark: #070b10;
  --api-text: #f1f5f7;
  --api-muted: #8fa0af;
  --api-yellow: #e0a126;
  --api-red: #e35d52;
  --api-green: #45b779;
  --api-cyan: #4eb5cc;
  --api-blue: #285993;
  display: block;
  width: 100%;
  max-width: 1680px;
  min-height: 100vh;
  margin: 0 auto;
  padding: 12px clamp(12px, 1.6vw, 24px) 18px;
  color: var(--api-text);
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  background:
    radial-gradient(circle at 48% -12%, rgba(65, 89, 112, 0.22), transparent 38%),
    var(--api-bg);
}

.app-header {
  min-height: 52px;
  margin-bottom: 10px;
  padding: 2px 2px 10px;
  border-bottom: 1px solid rgba(143, 160, 175, 0.16);
}

.eyebrow,
.panel-kicker {
  color: var(--api-yellow);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

.app-title {
  margin: 3px 0 0;
  color: var(--api-text);
  font-size: clamp(1.2rem, 1.8vw, 1.65rem);
  font-weight: 650;
  letter-spacing: -0.035em;
}

.header-status {
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid rgba(143, 160, 175, 0.18);
  border-radius: 999px;
  background: rgba(21, 29, 39, 0.72);
  color: #c9d2d9;
  font-size: 0.78rem;
  font-weight: 600;
  backdrop-filter: blur(12px);
}

.run-state-controls {
  display: inline-flex;
  gap: 6px;
}

.state-control {
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(143, 160, 175, 0.24);
  border-radius: 8px;
  background: var(--api-panel-dark);
  color: var(--api-text);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

.state-control:hover:not(:disabled) {
  border-color: rgba(224, 161, 38, 0.62);
  color: #efb23e;
}

.state-control.active {
  border-color: rgba(224, 161, 38, 0.7);
  background: rgba(224, 161, 38, 0.14);
  color: #efb23e;
}

.state-control:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.admin-link {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  padding: 0 12px;
  border: 1px solid rgba(224, 161, 38, 0.3);
  border-radius: 999px;
  background: rgba(224, 161, 38, 0.08);
  color: #efb23e;
  font-size: 0.76rem;
  font-weight: 700;
  text-decoration: none;
}

.admin-link:hover {
  border-color: rgba(224, 161, 38, 0.6);
  background: rgba(224, 161, 38, 0.14);
  color: #f3bf58;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--api-green);
  box-shadow: 0 0 0 4px rgba(69, 183, 121, 0.12);
}

.status-dot.is-paused { background: var(--api-yellow); box-shadow: 0 0 0 4px rgba(224, 161, 38, 0.12); }
.status-dot.is-fast_forward { background: var(--api-cyan); box-shadow: 0 0 0 4px rgba(78, 181, 204, 0.12); }
.status-dot.is-failed { background: var(--api-red); box-shadow: 0 0 0 4px rgba(227, 93, 82, 0.12); }
.status-dot.is-completed { background: #8fa0af; box-shadow: 0 0 0 4px rgba(143, 160, 175, 0.12); }

.header-divider {
  width: 1px;
  height: 16px;
  background: rgba(143, 160, 175, 0.22);
}

.simulator-grid {
  display: grid;
  grid-template-columns: minmax(255px, 0.68fr) repeat(2, minmax(360px, 1fr));
  grid-template-areas:
    "annulus gauges chart"
    "annulus choke chart";
  gap: 10px 14px;
  align-items: start;
}

.card,
.annulus-panel,
.choke-panel,
.pressure-chart-panel {
  width: 100%;
  max-width: none;
  padding: 18px;
  border: 1px solid rgba(143, 160, 175, 0.18);
  border-radius: 14px;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.025), transparent 42%),
    var(--api-panel);
  color: var(--api-text);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.2);
}

.panel-heading,
.annulus-header,
.chart-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-heading h2,
.annulus-header h2,
.chart-header h2 {
  margin: 2px 0 0;
  color: var(--api-text);
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: -0.01em;
  text-transform: none;
}

.value-badge {
  padding: 6px 9px;
  border: 1px solid rgba(224, 161, 38, 0.24);
  border-radius: 999px;
  background: rgba(224, 161, 38, 0.1);
  color: #f1bb51;
  font-size: 0.72rem;
  font-weight: 700;
  white-space: nowrap;
}

.annulus-panel {
  grid-area: annulus;
}

.choke-panel {
  grid-area: choke;
  padding: 14px;
}

.gauges-panel {
  grid-area: gauges;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 12px;
  padding: 10px 14px 6px;
}

.gauges-heading {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 0;
}

.gauges-heading h2 {
  margin: 2px 0 0;
  color: var(--api-text);
  font-size: 0.9rem;
  font-weight: 650;
}

.gauges-unit {
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--api-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.pressure-chart-panel {
  grid-area: chart;
}

.gauges-panel :deep(.gauge-card) {
  width: 100%;
  max-width: none;
  padding: 0 6px 2px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.gauges-panel :deep(.gauge-card h1) {
  margin-bottom: -3px;
  font-size: 0.68rem;
}

.gauges-panel :deep(.gauge) {
  width: 100%;
  height: clamp(124px, 18vh, 156px);
  aspect-ratio: auto;
}

.choke-indicator,
.choke-visual,
.pump-inline-panel {
  border: 1px solid rgba(143, 160, 175, 0.14);
  border-radius: 10px;
  background: var(--api-panel-dark);
  box-shadow: none;
}

.choke-inline-panel {
  margin-bottom: 8px;
  padding: 9px;
  border: 1px solid rgba(143, 160, 175, 0.14);
  border-radius: 10px;
  background: var(--api-panel-dark);
}

.control-section-heading {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  color: var(--api-text);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.choke-indicator {
  margin-bottom: 8px;
  padding: 6px 8px;
}

.choke-indicator-head {
  margin-bottom: 2px;
}

.choke-indicator-title {
  font-size: 0.76rem;
}

.choke-speed-heading {
  font-size: 0.68rem;
}

.choke-gauge {
  max-height: 96px;
}

.choke-speed-panel {
  padding: 3px 6px;
}

.choke-speed-option {
  min-height: 14px;
}

.choke-speed-detent {
  width: 42px;
  height: 10px;
}

.choke-speed-hint {
  font-size: 0.62rem;
}

.choke-visual {
  overflow: hidden;
  height: 116px;
  margin-bottom: 8px;
}

.choke-zone-label {
  font-size: 0.95rem;
}

.choke-slot {
  bottom: 15px;
  width: 160px;
  height: 8px;
}

.choke-handle {
  bottom: 19px;
  width: 9px;
  height: 72px;
}

.choke-knob {
  top: -9px;
  width: 23px;
  height: 23px;
}

.pump-inline-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(150px, 0.85fr);
  gap: 8px 10px;
  margin-top: 0;
  padding: 9px;
}

.pump-metrics {
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 0;
}

.pump-metric {
  padding: 6px 8px;
  border-color: rgba(143, 160, 175, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  font-size: 0.78rem;
}

.pump-controls {
  gap: 6px;
}

.pump-regulator {
  display: flex;
  min-height: 32px;
  min-width: 94px;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border: 1px solid var(--api-border);
  border-radius: 3px;
  background: #eef2f6;
  color: #53606e;
  font-size: 0.68rem;
  font-weight: 700;
}

.pump-button.btn {
  min-height: 32px;
  padding: 3px 8px;
  border-radius: 8px;
  box-shadow: none;
}

.pump-button.btn-warning {
  border-color: var(--api-yellow);
  background: var(--api-yellow);
  color: #17110a;
}

.mud-switch.btn {
  min-height: 32px;
  margin-top: 0;
  padding: 4px 7px;
  border-color: rgba(143, 160, 175, 0.18);
  border-radius: 8px;
  box-shadow: none;
  font-size: 0.74rem;
}

.mud-switch-track {
  width: 44px;
  height: 20px;
}

.mud-switch-track i {
  width: 18px;
  height: 14px;
}

.mud-switch.heavy .mud-switch-track i {
  transform: translateX(22px);
}

.pressure-summary {
  min-width: 132px;
  margin: 0;
  font-size: 0.76rem;
}

.annulus-legend {
  padding: 8px 9px;
  border-radius: 8px;
  background: var(--api-panel-dark);
}

.annulus-column {
  height: min(64vh, 590px);
  min-height: 430px;
  border: 1px solid rgba(143, 160, 175, 0.25);
  border-radius: 9px;
  background: #272e33;
  overflow: hidden;
}

.pressure-chart {
  border-color: rgba(143, 160, 175, 0.12);
  border-radius: 9px;
  background: #0c131b;
}

.chart-header strong {
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.78rem;
}

@media (max-width: 1180px) {
  .simulator-grid {
    grid-template-columns: minmax(240px, 0.75fr) minmax(420px, 1.25fr);
    grid-template-areas:
      "annulus gauges"
      "annulus choke"
      "chart chart";
  }
}

@media (max-height: 720px) and (min-width: 761px) {
  .gauges-panel :deep(.gauge) {
    height: 108px;
  }

  .app-header {
    min-height: 46px;
    margin-bottom: 8px;
    padding-bottom: 7px;
  }
}

@media (max-width: 760px) {
  .page {
    padding-inline: 12px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .run-state-controls {
    order: 2;
  }

  .simulator-grid {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "gauges"
      "choke"
      "annulus"
      "chart";
  }

  .gauges-panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .annulus-column {
    height: 560px;
  }

  .pump-inline-panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .pump-metrics {
    grid-column: auto;
  }
}

/* Minimal SLB-inspired visual system */
:global(html),
:global(body) {
  background: #f4f6f8;
}

.page {
  --api-bg: #f4f6f8;
  --api-panel: #ffffff;
  --api-panel-dark: #f4f6f8;
  --api-panel-soft: #e9edf2;
  --api-border: #d8dee6;
  --api-border-dark: #b9c3cf;
  --api-text: #18212b;
  --api-muted: #66717f;
  --api-yellow: #0057b8;
  --api-red: #c83b32;
  --api-green: #25835b;
  --api-cyan: #48a9c5;
  --api-blue: #003f87;
  background: var(--api-bg);
}

.app-header {
  border-bottom-color: var(--api-border);
}

.run-result-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid #d6a5a1;
  border-left: 4px solid var(--api-red);
  border-radius: 3px;
  background: #fbefee;
  color: #752822;
}

.run-result-banner > div {
  display: grid;
  gap: 2px;
}

.run-result-banner span {
  font-size: 0.78rem;
}

.run-result-banner a {
  flex: 0 0 auto;
  padding: 7px 10px;
  border-radius: 3px;
  background: #0057b8;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 700;
  text-decoration: none;
}

.run-result-banner.is-completed {
  border-color: #b8c9df;
  border-left-color: #0057b8;
  background: #e8f1fb;
  color: #003f87;
}

.finish-control {
  border-color: #0057b8;
  color: #0057b8;
}

.finish-control:hover:not(:disabled) {
  background: #0057b8;
  color: #ffffff;
}

.eyebrow,
.panel-kicker {
  color: var(--api-yellow);
}

.header-status,
.state-control,
.admin-link,
.card,
.annulus-panel,
.choke-panel,
.pressure-chart-panel,
.choke-inline-panel,
.choke-indicator,
.choke-visual,
.pump-inline-panel,
.pump-metric,
.annulus-legend,
.pressure-chart,
.choke-gauge-shell,
.choke-speed-panel,
.mud-switch,
.pump-button {
  background: var(--api-panel);
  box-shadow: none;
  backdrop-filter: none;
}

.card,
.annulus-panel,
.choke-panel,
.pressure-chart-panel {
  border-color: var(--api-border);
  border-radius: 4px;
}

.header-status,
.state-control,
.admin-link,
.value-badge,
.choke-inline-panel,
.choke-indicator,
.choke-visual,
.pump-inline-panel,
.pump-metric,
.annulus-legend,
.pressure-chart,
.choke-gauge-shell,
.choke-speed-panel,
.mud-switch.btn,
.pump-button.btn,
.chart-header strong,
.gauges-unit {
  border-radius: 3px;
}

.header-status,
.state-control,
.mud-switch,
.pump-button,
.choke-speed-detent,
.choke-gauge-shell,
.choke-speed-panel {
  border-color: var(--api-border);
  color: var(--api-text);
}

.admin-link,
.value-badge,
.state-control.active {
  border-color: #0057b8;
  background: #e8f1fb;
  color: #004b9e;
}

.admin-link:hover,
.state-control:hover:not(:disabled) {
  border-color: #003f87;
  background: #dceaf8;
  color: #003f87;
}

.status-dot,
.status-dot.is-paused,
.status-dot.is-fast_forward,
.status-dot.is-failed,
.status-dot.is-completed {
  box-shadow: none;
}

.header-divider {
  background: var(--api-border);
}

.choke-hit-area.left,
.choke-hit-area.right {
  opacity: 1;
  z-index: 0;
}

.choke-visual {
  background: #f1f4f7;
  border-color: #c7d0da;
}

.choke-hit-area.left {
  background: #f5e8e7;
  border-right: 1px solid #c7d0da;
}

.choke-hit-area.right {
  background: #e6f2eb;
}

.choke-zone-label {
  text-shadow: none;
}

.choke-slot {
  background: #d8dee6;
  box-shadow: none;
}

.choke-handle {
  background: #111820;
  box-shadow: none;
}

.choke-knob {
  background: #05080b;
  border: 2px solid #c7d0da;
  box-shadow: none;
}

.mud-switch-track i {
  background: #ffffff;
  border-color: #9ba7b4;
  box-shadow: none;
}

.mud-switch-track,
.mud-switch.heavy .mud-switch-track {
  background: #d8dee6;
  border-color: #b9c3cf;
  box-shadow: none;
}

.mud-switch.heavy {
  border-color: #0057b8;
  background: #e8f1fb;
}

.choke-speed-detent {
  background: #e1e6ec;
  box-shadow: none;
}

.choke-speed-option input:checked + .choke-speed-detent,
.pump-button.btn-warning {
  border-color: #0057b8;
  background: #0057b8;
  color: #ffffff;
  box-shadow: none;
}

.chart-grid {
  display: none;
}

.pressure-chart {
  background: #ffffff;
}

.chart-axis {
  stroke: #9ba7b4;
}

.chart-line,
.choke-gauge-arc {
  stroke: #0057b8;
}

.choke-gauge-value {
  fill: #0057b8;
}

.chart-dot {
  fill: #0057b8;
  stroke: #ffffff;
}

.legend-swatch.gas {
  background: #d69a24;
}
</style>
