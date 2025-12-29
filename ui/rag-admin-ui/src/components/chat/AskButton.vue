<script setup>
const props = defineProps({
  disabled: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['click'])
</script>

<template>
  <div class="flex justify-end">
    <button
      class="rounded-full border border-emerald-400 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-300 hover:border-emerald-200"
      type="button"
      :disabled="props.disabled"
      @click="emit('click')"
    >
      Ask
    </button>
  </div>
</template>