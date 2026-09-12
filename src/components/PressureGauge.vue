<template>
  <div class="gauge-card" :style="cardStyle">
    <h1 :style="titleStyle">{{ resolved.title }}</h1>

    <svg :viewBox="resolved.gauge.viewBox" class="gauge">
      <path :d="arcPath" class="arc arc-main" :style="arcStyle" />

      <g>
        <line
          v-for="tick in ticks"
          :key="tick.value"
          :x1="tick.x1"
          :y1="tick.y1"
          :x2="tick.x2"
          :y2="tick.y2"
          class="tick"
          :style="tickStyle"
        />
        <text
          v-for="tick in ticks"
          :key="`label-${tick.value}`"
          :x="tick.lx"
          :y="tick.ly"
          text-anchor="middle"
          class="tick-label"
          :style="tickLabelStyle"
        >
          {{ tick.value }}
        </text>
      </g>

      <line :x1="cx" :y1="cy" :x2="needle.x" :y2="needle.y" class="needle" :style="needleStyle" />
      <circle :cx="cx" :cy="cy" :r="resolved.gauge.centerDotRadius" class="needle-center" :style="needleCenterStyle" />

      <text :x="cx" :y="cy + resolved.gauge.valueYOffset" text-anchor="middle" class="value" :style="valueStyle">
        {{ formattedPressure }} {{ resolved.unit }}
      </text>
    </svg>
  </div>
</template>

<script>
const defaults = {
  title: 'Pressure Gauge',
  unit: 'PSI',
  pressure: 0,
  minPressure: 0,
  maxPressure: 300,
  tickValues: [0, 50, 100, 150, 200, 250, 300],
  id: '',
  colors: {
    backgroundStart: '#202832',
    backgroundEnd: '#161d25',
    cardBackground: '#ffffff',
    cardBorder: '#d8dee6',
    cardShadow: 'transparent',
    title: '#0057b8',
    arc: '#0057b8',
    tick: '#66717f',
    tickLabel: '#66717f',
    needle: '#18212b',
    value: '#18212b',
  },
  gauge: {
    viewBox: '0 0 300 270',
    cx: 150,
    cy: 160,
    arcRadius: 110,
    strokeWidth: 5,
    centerDotRadius: 10,
    valueYOffset: 50,
    sweepStartDeg: 225,
    sweepSizeDeg: 270,
    needleInset: 10,
    tickOuterOffset: 2,
    tickInnerOffset: 14,
    labelInset: 28,
  },
}

function mergeConfig(base, input) {
  return {
    ...base,
    ...input,
    colors: {
      ...base.colors,
      ...(input.colors || {}),
    },
    gauge: {
      ...base.gauge,
      ...(input.gauge || {}),
    },
  }
}

export default {
  props: {
    config: {
      type: Object,
      required: true,
    },
    value: {
      type: Number,
      default: null,
    },
  },
  data() {
    return {
      currentPressure: 0,
    }
  },
  computed: {
    resolved() {
      return mergeConfig(defaults, this.config || {})
    },
    cx() {
      return this.resolved.gauge.cx
    },
    cy() {
      return this.resolved.gauge.cy
    },
    arcRadius() {
      return this.resolved.gauge.arcRadius
    },
    displayPressure() {
      if (typeof this.value === 'number' && Number.isFinite(this.value)) {
        return this.clampPressure(this.value)
      }
      return this.currentPressure
    },
    formattedPressure() {
      return this.displayPressure.toFixed(1)
    },
    pressureRatio() {
      const min = this.resolved.minPressure
      const max = this.resolved.maxPressure
      const ratio = (this.displayPressure - min) / (max - min)
      return Math.min(1, Math.max(0, ratio))
    },
    pressureAngleRad() {
      const start = (this.resolved.gauge.sweepStartDeg * Math.PI) / 180
      const sweep = (this.resolved.gauge.sweepSizeDeg * Math.PI) / 180
      return start - this.pressureRatio * sweep
    },
    arcPath() {
      const startDeg = this.resolved.gauge.sweepStartDeg
      const endDeg = startDeg - this.resolved.gauge.sweepSizeDeg
      const start = this.pointOnCircle(startDeg, this.arcRadius)
      const end = this.pointOnCircle(endDeg, this.arcRadius)
      const largeArcFlag = this.resolved.gauge.sweepSizeDeg > 180 ? 1 : 0
      return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} A ${this.arcRadius} ${this.arcRadius} 0 ${largeArcFlag} 1 ${end.x.toFixed(1)} ${end.y.toFixed(1)}`
    },
    needle() {
      const radius = this.arcRadius - this.resolved.gauge.needleInset
      return {
        x: this.cx + radius * Math.cos(this.pressureAngleRad),
        y: this.cy - radius * Math.sin(this.pressureAngleRad),
      }
    },
    ticks() {
      return this.resolved.tickValues.map((value) => {
        const min = this.resolved.minPressure
        const max = this.resolved.maxPressure
        const ratio = (value - min) / (max - min)
        const start = (this.resolved.gauge.sweepStartDeg * Math.PI) / 180
        const sweep = (this.resolved.gauge.sweepSizeDeg * Math.PI) / 180
        const angle = start - ratio * sweep
        const outer = this.arcRadius + this.resolved.gauge.tickOuterOffset
        const inner = this.arcRadius - this.resolved.gauge.tickInnerOffset
        const labelRadius = this.arcRadius - this.resolved.gauge.labelInset
        return {
          value,
          x1: this.cx + outer * Math.cos(angle),
          y1: this.cy - outer * Math.sin(angle),
          x2: this.cx + inner * Math.cos(angle),
          y2: this.cy - inner * Math.sin(angle),
          lx: this.cx + labelRadius * Math.cos(angle),
          ly: this.cy - labelRadius * Math.sin(angle) + 4,
        }
      })
    },
    gaugeBounds() {
      const parts = String(this.resolved.gauge.viewBox || '')
        .trim()
        .split(/\s+/)
        .map((value) => Number(value))
      const width = Number.isFinite(parts[2]) ? parts[2] : 220
      const height = Number.isFinite(parts[3]) ? parts[3] : 200

      return { width, height }
    },
    cardStyle() {
      return {
        '--card-bg': this.resolved.colors.cardBackground,
        '--card-border': this.resolved.colors.cardBorder,
        '--card-shadow': this.resolved.colors.cardShadow,
        '--card-width': `${this.gaugeBounds.width + 24}px`,
        '--gauge-aspect-ratio': `${this.gaugeBounds.width} / ${this.gaugeBounds.height}`,
      }
    },
    titleStyle() {
      return { '--title-color': this.resolved.colors.title }
    },
    arcStyle() {
      return {
        '--arc-color': this.resolved.colors.arc,
        '--arc-width': `${this.resolved.gauge.strokeWidth}px`,
      }
    },
    tickStyle() {
      return { '--tick-color': this.resolved.colors.tick }
    },
    tickLabelStyle() {
      return { '--tick-label-color': this.resolved.colors.tickLabel }
    },
    needleStyle() {
      return { '--needle-color': this.resolved.colors.needle }
    },
    needleCenterStyle() {
      return { '--needle-center-color': this.resolved.colors.needle }
    },
    valueStyle() {
      return { '--value-color': this.resolved.colors.value }
    },
  },
  watch: {
    config: {
      deep: true,
      immediate: true,
      handler() {
        this.currentPressure = this.clampPressure(this.resolved.pressure)
      },
    },
  },
  methods: {
    pointOnCircle(deg, radius) {
      const rad = (deg * Math.PI) / 180
      return {
        x: this.cx + radius * Math.cos(rad),
        y: this.cy - radius * Math.sin(rad),
      }
    },
    clampPressure(value) {
      return Math.min(this.resolved.maxPressure, Math.max(this.resolved.minPressure, value))
    },
  },
}
</script>

<style scoped>
.gauge-card {
  box-sizing: border-box;
  width: min(92vw, var(--card-width));
  padding: 12px 12px 10px;
  border-radius: 6px;
  border: 3px solid var(--card-border);
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.055), transparent 58%),
    linear-gradient(180deg, var(--card-bg), #161d25);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.06),
    inset 0 0 0 4px rgba(0, 0, 0, 0.22),
    0 18px 36px var(--card-shadow);
}

h1 {
  margin: 0 0 8px;
  text-align: center;
  font-size: 0.9rem;
  color: var(--title-color);
  text-transform: uppercase;
}

.gauge {
  display: block;
  width: 100%;
  aspect-ratio: var(--gauge-aspect-ratio);
  height: auto;
}

.arc {
  fill: none;
  stroke-linecap: round;
}

.arc-main {
  stroke: var(--arc-color);
  stroke-width: var(--arc-width);
}

.tick {
  stroke: var(--tick-color);
  stroke-width: 2;
}

.needle {
  stroke: var(--needle-color);
  stroke-width: 3;
  stroke-linecap: round;
}

.needle-center {
  fill: var(--needle-center-color);
}

.value {
  font-size: 14px;
  font-weight: 700;
  fill: var(--value-color);
}

.tick-label {
  font-size: 9px;
  font-weight: 600;
  fill: var(--tick-label-color);
}
</style>
