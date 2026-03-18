<script setup>
defineProps({
  labelShort: { type: String, required: true },
  size: { type: Number, default: 120 },
});

// Deterministic color from string
function colorFromString(str) {
  const colors = [
    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
    "#f97316",
    "#6366f1",
  ];
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="`0 0 ${size} ${size}`"
    xmlns="http://www.w3.org/2000/svg"
    style="border-radius: 8px; display: block"
  >
    <rect :width="size" :height="size" :fill="colorFromString(labelShort)" opacity="0.15" />
    <text
      :x="size / 2"
      :y="size / 2"
      text-anchor="middle"
      dominant-baseline="central"
      :fill="colorFromString(labelShort)"
      :font-size="size * 0.35"
      font-weight="700"
      font-family="system-ui, sans-serif"
    >
      {{ labelShort }}
    </text>
  </svg>
</template>
