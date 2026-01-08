<script setup>
    import { computed, ref } from 'vue'
    
    const props = defineProps({
      sources: {
        type: Array,
        default: () => [],
      },
    })
    
    const expandedSources = ref([])
    const expandedEntries = ref(new Set())
    
    const groupedSources = computed(() => {
      const map = new Map()
      const sources = props.sources || []
    
      sources.forEach((source) => {
        const key = (source?.source || '').toString() || 'Unknown source'
        if (!map.has(key)) {
          map.set(key, new Set())
        }
        const entry = (source?.content || '').toString() || 'Empty content'
        map.get(key).add(entry)
      })
    
      return Array.from(map.entries()).map(([key, contents]) => ({
        key,
        count: contents.size,
        entries: Array.from(contents),
      }))
    })
    
    function toggleSourceGroup(key) {
      expandedSources.value = expandedSources.value.includes(key)
        ? expandedSources.value.filter((k) => k !== key)
        : [...expandedSources.value, key]
    }
    
    function isGroupExpanded(key) {
      return expandedSources.value.includes(key)
    }
    
    function prettySource(raw) {
      const value = (raw?.source || raw || '').toString()
      if (!value) return 'Unknown source'
      const clean = value.split('?')[0]
      return clean.split('/').pop() || clean
    }
    
    function entryKey(groupKey, entry) {
      return `${groupKey}::${entry.slice(0, 80)}::${entry.length}`
    }
    
    function isEntryExpanded(groupKey, entry) {
      return expandedEntries.value.has(entryKey(groupKey, entry))
    }
    
    function toggleEntry(groupKey, entry) {
      const key = entryKey(groupKey, entry)
      const next = new Set(expandedEntries.value)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      expandedEntries.value = next
    }
    
    function preview(entry, max = 240) {
      const text = (entry || '').toString().trim()
      if (text.length <= max) return text
      return text.slice(0, max) + '…'
    }
    </script>
    
    <template>
      <div class="mt-4">
        <div class="text-xs uppercase tracking-[0.3em] text-slate-500">
          Sources
        </div>
    
        <template v-if="groupedSources.length">
          <div class="mt-2 flex flex-col gap-2">
            <div
              v-for="group in groupedSources"
              :key="group.key"
              class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
            >
            <button
  type="button"
  class="flex w-full items-center gap-3 text-sm font-medium text-slate-100"
  @click="toggleSourceGroup(group.key)"
>
  <span class="min-w-0 flex-1 truncate">
    {{ prettySource({ source: group.key }) }} ×{{ group.count }}
  </span>

  <span class="shrink-0 text-[0.6rem] text-slate-500">
    {{ isGroupExpanded(group.key) ? 'Collapse' : 'Expand' }}
  </span>
</button>

    
              <div
                v-if="isGroupExpanded(group.key)"
                class="mt-2 space-y-2 text-[0.7rem] text-slate-300 pr-1"

              >
                <div
                  v-for="entry in group.entries"
                  :key="entry"
                  class="rounded-md border border-slate-800 bg-slate-950/60 p-2"
                >
                <div class="whitespace-pre-wrap break-all font-mono leading-5">

                    {{ isEntryExpanded(group.key, entry) ? entry : preview(entry) }}
                  </div>
    
                  <button
                    v-if="entry && entry.length > 240"
                    type="button"
                    class="mt-2 text-[0.65rem] text-slate-400 hover:text-white"
                    @click="toggleEntry(group.key, entry)"
                  >
                    {{ isEntryExpanded(group.key, entry) ? 'Show less' : 'Show more' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
    
        <p v-else class="mt-2 text-xs text-slate-500 italic">No sources for this note.</p>
      </div>
    </template>
    