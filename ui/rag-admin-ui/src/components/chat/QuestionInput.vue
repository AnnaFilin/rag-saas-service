<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

function updateValue(value) {
  emit('update:modelValue', value)
}
</script>

<template>

  <label class="text-sm font-semibold text-slate-300">Question</label>

  <div class="relative">
    <textarea :value="props.modelValue" @input="updateValue($event.target.value)"
      class="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 pr-16 text-sm text-white focus:outline-none focus:ring-2 focus:ring-slate-500"
      rows="3" placeholder="Type your question..."></textarea>

    <button v-if="props.modelValue" type="button" @click="updateValue('')"
      class="absolute bottom-2 right-2 rounded-md px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-700">
      Clear
    </button>
  </div>


</template>