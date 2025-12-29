<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: {
    type: String,
    default: '',
  },
  variant: {
    type: String,
    required: true,
  },
})

const variantClass = computed(() => {
  return props.variant === 'error'
    ? 'rounded-md border border-red-600 bg-red-700/40 px-4 py-2 text-sm text-red-200'
    : 'rounded-md border border-emerald-500 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200'
})
</script>

<template>
  <div v-if="props.text" :class="variantClass">
    {{ props.text }}
  </div>
</template>

