import { useMemo, useState, useEffect, memo } from 'react';
import ReactApexChart from 'react-apexcharts';

function getThemeColors() {
  const style = getComputedStyle(document.documentElement);
  return {
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
}

function getCurrentTheme() {
  return document.documentElement.getAttribute('data-bs-theme') || 'dark';
}

const useThemeColors = () => {
  const [colors, setColors] = useState(getThemeColors);
  const [themeMode, setThemeMode] = useState(getCurrentTheme);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setColors(getThemeColors());
      setThemeMode(getCurrentTheme());
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
    return () => observer.disconnect();
  }, []);

  return { colors, themeMode };
};

const baseOptions = (colors, themeMode) => ({
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
    borderColor: colors.border,
    strokeDashArray: 3,
  },
  legend: {
    labels: { colors: colors.textSecondary },
  },
  tooltip: {
    theme: themeMode,
    style: { fontSize: '12px' },
  },
});

export const AreaChart = memo(({ data, height = 200, title }) => {
  const { colors, themeMode } = useThemeColors();
  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    colors: [colors.accent],
    chart: { ...baseOptions(colors, themeMode).chart, type: 'area', height },
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
    grid: { ...baseOptions(colors, themeMode).grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    theme: { mode: themeMode },
  }), [colors, themeMode, data, height]);

  const series = useMemo(() => [{ name: title || 'Ventas', data: data.map((d) => d.value) }], [data, title]);

  return <ReactApexChart options={options} series={series} type="area" height={height} />;
});

AreaChart.displayName = 'AreaChart';

export const DonutChart = memo(({ data, height = 250, title }) => {
  const { colors, themeMode } = useThemeColors();
  const chartColors = [colors.accent, colors.green, colors.orange, colors.red, '#7e22ce', '#06b6d4', '#f59e0b', '#ec4899'];

  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    colors: chartColors,
    chart: { ...baseOptions(colors, themeMode).chart, type: 'donut', height },
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
      ...baseOptions(colors, themeMode).tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: themeMode },
  }), [colors, themeMode, data, height]);

  const series = useMemo(() => data.map((d) => d.value), [data]);

  return <ReactApexChart options={options} series={series} type="donut" height={height} />;
});

DonutChart.displayName = 'DonutChart';

export const HorizontalBarChart = memo(({ data, height = 250, title }) => {
  const { colors, themeMode } = useThemeColors();
  const chartColors = [colors.accent, colors.green, colors.orange, colors.red, '#7e22ce'];

  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    colors: chartColors,
    chart: { ...baseOptions(colors, themeMode).chart, type: 'bar', height },
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
      ...baseOptions(colors, themeMode).tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: themeMode },
  }), [colors, themeMode, data, height]);

  const series = useMemo(() => [{ name: title || 'Cantidad', data: data.map((d) => d.value) }], [data, title]);

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
});

HorizontalBarChart.displayName = 'HorizontalBarChart';

export const LineChart = memo(({ datasets, categories, height = 250, title }) => {
  const { colors, themeMode } = useThemeColors();

  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    chart: { ...baseOptions(colors, themeMode).chart, type: 'line', height },
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
    grid: { ...baseOptions(colors, themeMode).grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    markers: { size: 3, strokeWidth: 0 },
    theme: { mode: themeMode },
  }), [colors, themeMode, categories, height]);

  return <ReactApexChart options={options} series={datasets} type="line" height={height} />;
});

LineChart.displayName = 'LineChart';

export const BarChart = memo(({ data, height = 250, title, colors: customColors }) => {
  const { colors, themeMode } = useThemeColors();
  const chartColors = customColors || [colors.green, colors.accent, colors.orange, colors.red, '#7e22ce'];

  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    colors: chartColors,
    chart: { ...baseOptions(colors, themeMode).chart, type: 'bar', height },
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
        style: { colors: colors.textMuted, fontSize: '11px' },
        rotate: -45,
        rotateAlways: false,
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: colors.textMuted, fontSize: '11px' },
        formatter: (v) => `$${(v / 1000).toFixed(0)}k`,
      },
    },
    grid: { ...baseOptions(colors, themeMode).grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      ...baseOptions(colors, themeMode).tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: themeMode },
  }), [colors, themeMode, data, height, customColors]);

  const series = useMemo(() => [{ name: title || 'Valor', data: data.map((d) => d.value) }], [data, title]);

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
});

BarChart.displayName = 'BarChart';

export const SalesByHourChart = memo(({ data, height = 200 }) => {
  const { colors, themeMode } = useThemeColors();

  const options = useMemo(() => ({
    ...baseOptions(colors, themeMode),
    colors: [colors.orange],
    chart: { ...baseOptions(colors, themeMode).chart, type: 'bar', height },
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
    grid: { ...baseOptions(colors, themeMode).grid, yaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      ...baseOptions(colors, themeMode).tooltip,
      y: { formatter: (v) => v.toLocaleString() },
    },
    theme: { mode: themeMode },
  }), [colors, themeMode, data, height]);

  const series = useMemo(() => [{ name: 'Ventas', data: data.map((d) => d.value) }], [data]);

  return <ReactApexChart options={options} series={series} type="bar" height={height} />;
});

SalesByHourChart.displayName = 'SalesByHourChart';
