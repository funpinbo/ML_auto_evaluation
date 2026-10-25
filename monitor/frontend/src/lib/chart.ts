// ECharts 는 필요한 모듈만 등록한다 (번들 크기)
import { BarChart, GaugeChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, GaugeChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export { echarts }
export const PALETTE = ['#73bf69', '#5794f2', '#ff9830', '#b877d9', '#f2cc0c', '#8ab8ff', '#ff7383']
