<script setup>
    import AnswerSources from './AnswerSources.vue'
    
    const props = defineProps({
      lastQuestion: { type: String, default: '' },
      answer: { type: String, default: '' },
      sources: { type: Array, default: () => [] },
    })
    </script>
    
    <template>
      <div class="flex-1 rounded-lg border border-slate-800 bg-slate-950 p-4 text-sm text-slate-100">
        <div class="flex flex-col gap-3">
          <div
            v-if="props.lastQuestion"
            class="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3"
          >
            <div class="text-[0.7rem] tracking-[0.18em] uppercase text-slate-500">
              Question
            </div>
            <div class="mt-2 whitespace-pre-wrap text-slate-100">
              {{ props.lastQuestion }}
            </div>
          </div>
    
          <div
            v-if="props.answer"
            class="rounded-lg border border-slate-800 bg-slate-950 px-4 py-3"
          >
            <div class="text-[0.7rem] tracking-[0.18em] uppercase text-slate-500">
              Answer
            </div>
            <div class="mt-2 whitespace-pre-wrap text-slate-100">
              {{ props.answer }}
            </div>
          </div>
    
          <AnswerSources :sources="props.sources" :answer="props.answer" />
        </div>
      </div>
    </template>
    