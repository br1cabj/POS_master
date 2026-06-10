import React, { useMemo } from 'react';
import ReactApexChart from 'react-apexcharts';

let _cachedColors = null;
let _cachedTheme = null;

const getThemeColors = () => {
  const theme = document.documentElement.getAttribute('data-bs-theme') || 'dark';
  if (_cachedColors && _cachedTheme === theme) return _cachedColors;
  const style = getComputedStyle(document.documentElement);
  _cachedColors = {
    accent: style.getPropertyValue('--accent').trim() || '#2563eb',
    accentText: style.getPropertyValue('--accent-text').trim() || '#60a5fa',
    green: style.getPropertyValue('--green-text').trim() || '#4ade80',
    orange: style.getPropertyValue('--orange-text').trim() || '#fbbf24',
    red: style.getPropertyValue('--red-text').trim() || '#f87171',
    textPrimary: style.getPropertyValue('--text-primary').trim() || '#f0f0f0',
    textSecondary: style.getPropertyValue('--text-secondary').trim() || '#888888',
    textMuted: style.getPropertyValue('--text-muted').trim() || '#737373',
    surface2: style.getPropertyValue('--surface-2').trim() || '#1e1e1e',
    surface3: style.getPropertyValue('--surface-3').trim() || '#252525',
    border: style.getPropertyValue('--border').trim() || '#2a2a2a',
  };
  _cachedTheme = theme;
  return _cachedColors;
};

const useThemeColors = () => useMemo(() => getThemeColors(), []);

const defaultOptions = {
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    animations: {
      enabled: true,
      easing: 'easeinout',
      speed: 800,
    },
  },
  grid: {
    borderColor: 'var(--border)',
    strokeDashArray: 3,
  },
  legend: {
    labels: { colors: 'var(--text-secondary)' },
  },
  tooltip: {
    theme: 'dark',
    style: { fontSize: '12px' },
  },
};

export const AreaChart = ({ data, height = 200, title }) => {
  const colors = useThemeColors();
  const options = {
    ...defaultOptions,
    colors: [colors.accent],
    chart: { ...defaultOptions.chart, type: 'area', height },
    stroke: { curve: 'smooth', width: 2 },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.7,
        opacityTo: 0.1,
        stops: [0, 90, 100],
      },
    },
    xaxis: {
      categories: data.map((d) => d.label),
      labels: { style: { colors: colors.textMuted, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: colors.textMuted, fontSize: '11px' },
        formatter: (v) => `$${(v / 1000).toFixed(0)}k`,
      },
    },
    grid: { ...defaultOptions.grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    theme: { mode: 'dark' },
  };

  const series = [{ name: title || 'Ventas', data: data.map((d) => d.value) }];

  return <ReactApexChart options={options} series={series} type="area" height={height} />;
};

export const DonutChart = ({ data, height = 250, title }) => {
  const colors = useThemeColors();
  const chartColors = [colors.accent, colors.green, colors.orange, colors.red, '#7e22ce', '#06b6d4', '#f59e0b', '#ec4899'];

  const options = {
    ...defaultOptions,
    colors: chartColors,
    chart: { ...defaultOptions.chart, type: 'donut', height },
    labels: data.map((d) => d.label),
    legend: {
      position: 'bottom',
      labels: { colors: colors.textSecondary },
      fontSize: '11px',
    },
    plotOptions: {
      pie: {
        donut: {
          size: '65%',
          labels: {
            show: true,
            total: {
              show: true,
              label: 'Total',
              color: colors.textMuted,
              fontSize: '11px',
              formatter: (w) => {
                const total = w.globals.seriesTotals.reduce((a, b) => a + b, 0);
                return total.toLocaleString();
              },
            },
          },
        },
      },
    },
    dataLabels: { enabled: false },
    stroke: { show: false },
    tooltip: {
      ...defaultOptions.tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: 'dark' },
  };

  const series = data.map((d) => d.value);

  return <ReactApexChart options={options} series={series} type="donut" height={height} />;
};

export const HorizontalBarChart = ({ data, height = 250, title }) => {
  const colors = useThemeColors();
  const chartColors = [colors.accent, colors.green, colors.orange, colors.red, '#7e22ce'];

  const options = {
    ...defaultOptions,
    colors: chartColors,
    chart: { ...defaultOptions.chart, type: 'bar', height },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 4,
        barHeight: '70%',
        distributed: true,
      },
    },
    xaxis: {
      categories: data.map((d) => d.label),
      labels: { style: { colors: colors.textMuted, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: { style: { colors: colors.textMuted, fontSize: '10px' } },
    },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      ...defaultOptions.tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: 'dark' },
  };

  const series = [{ name: title || 'Cantidad', data: data.map((d) => d.value) }];

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
};

export const LineChart = ({ datasets, categories, height = 250, title }) => {
  const colors = useThemeColors();

  const options = {
    ...defaultOptions,
    chart: { ...defaultOptions.chart, type: 'line', height },
    stroke: { curve: 'smooth', width: [2, 2] },
    xaxis: {
      categories,
      labels: { style: { colors: colors.textMuted, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: colors.textMuted, fontSize: '11px' },
        formatter: (v) => `$${(v / 1000).toFixed(0)}k`,
      },
    },
    grid: { ...defaultOptions.grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    markers: { size: 3, strokeWidth: 0 },
    theme: { mode: 'dark' },
  };

  return <ReactApexChart options={options} series={datasets} type="line" height={height} />;
};

export const BarChart = ({ data, height = 250, title, colors: customColors }) => {
  const themeColors = useThemeColors();
  const chartColors = customColors || [themeColors.green, themeColors.accent, themeColors.orange, themeColors.red, '#7e22ce'];

  const options = {
    ...defaultOptions,
    colors: chartColors,
    chart: { ...defaultOptions.chart, type: 'bar', height },
    plotOptions: {
      bar: {
        horizontal: false,
        borderRadius: 4,
        columnWidth: '60%',
        distributed: true,
      },
    },
    xaxis: {
      categories: data.map((d) => d.label),
      labels: {
        style: { colors: themeColors.textMuted, fontSize: '11px' },
        rotate: -45,
        rotateAlways: false,
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: themeColors.textMuted, fontSize: '11px' },
        formatter: (v) => `$${(v / 1000).toFixed(0)}k`,
      },
    },
    grid: { ...defaultOptions.grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      ...defaultOptions.tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: 'dark' },
  };

  const series = [{ name: title || 'Valor', data: data.map((d) => d.value) }];

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
};

export const SalesByHourChart = ({ data, height = 200 }) => {
  const colors = useThemeColors();

  const options = {
    ...defaultOptions,
    colors: [colors.orange],
    chart: { ...defaultOptions.chart, type: 'bar', height },
    plotOptions: {
      bar: {
        borderRadius: 4,
        columnWidth: '80%',
      },
    },
    xaxis: {
      categories: data.map((d) => d.label),
      labels: { style: { colors: colors.textMuted, fontSize: '10px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: colors.textMuted, fontSize: '11px' },
        formatter: (v) => `$${(v / 1000).toFixed(0)}k`,
      },
    },
    grid: { ...defaultOptions.grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      ...defaultOptions.tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: 'dark' },
  };

  const series = [{ name: 'Ventas', data: data.map((d) => d.value) }];

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
};
