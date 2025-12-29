<script setup>
const props = defineProps({
  ragMode: {
    type: String,
    required: true,
  },
  role: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['update:ragMode', 'update:role'])

function setMode(mode) {
  emit('update:ragMode', mode)
}

function updateRole(value) {
  emit('update:role', value)
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <label class="text-sm font-semibold text-slate-300">Mode</label>

    <div class="flex flex-wrap gap-2">
      <button
        type="button"
        class="px-3 py-1 text-xs rounded border"
        :class="props.ragMode === 'reference'
          ? 'bg-slate-800 border-slate-500 text-white'
          : 'bg-transparent border-slate-700 text-slate-400'"
        @click="setMode('reference')"
      >
        Reference
      </button>

      <button
        type="button"
        class="px-3 py-1 text-xs rounded border"
        :class="props.ragMode === 'synthesis'
          ? 'bg-slate-800 border-slate-500 text-white'
          : 'bg-transparent border-slate-700 text-slate-400'"
        @click="setMode('synthesis')"
      >
        Synthesis
      </button>

      <button
        type="button"
        class="px-3 py-1 text-xs rounded border"
        :class="props.ragMode === 'custom'
          ? 'bg-slate-800 border-slate-500 text-white'
          : 'bg-transparent border-slate-700 text-slate-400'"
        @click="setMode('custom')"
      >
        Custom
      </button>
    </div>

    <div v-if="props.ragMode === 'custom'" class="mt-2 flex flex-col gap-2">
      <label class="text-sm font-semibold text-slate-300">Role (custom)</label>
      <textarea
        v-model="props.role"
        class="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
        rows="3"
        placeholder="Custom instruction for the assistant..."
        @input="updateRole($event.target.value)"
      ></textarea>
    </div>
  </div>
</template>