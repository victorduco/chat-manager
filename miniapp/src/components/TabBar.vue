<template>
  <div class="tab-bar">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      :class="['tab-button', { active: activeTab === tab.id }]"
      @click="$emit('change', tab.id)"
    >
      <span class="tab-icon">{{ tab.icon }}</span>
      <span class="tab-label">{{ tab.label }}</span>
    </button>
  </div>
</template>

<script>
export default {
  name: 'TabBar',
  props: {
    activeTab: {
      type: String,
      required: true
    },
    tabs: {
      type: Array,
      required: true
    }
  }
}
</script>

<style scoped>
.tab-bar {
  display: flex;
  background: var(--tg-theme-bg-color, #ffffff);
  border-bottom: 1px solid var(--tg-theme-secondary-bg-color, #f0f0f0);
  overflow-x: auto;
  position: sticky;
  top: 64px;
  z-index: 99;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.tab-bar::-webkit-scrollbar {
  display: none;
}

.tab-button {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  border: none;
  background: transparent;
  color: var(--tg-theme-hint-color, #999999);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  position: relative;
}

.tab-button.active {
  color: var(--tg-theme-button-color, #3390ec);
}

.tab-button.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--tg-theme-button-color, #3390ec);
}

.tab-icon {
  font-size: 20px;
}

.tab-label {
  font-size: 12px;
  font-weight: 500;
}
</style>
