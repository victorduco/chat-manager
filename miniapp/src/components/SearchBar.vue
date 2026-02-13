<template>
  <div class="search-bar">
    <div class="search-input-wrapper">
      <span class="search-icon">🔍</span>
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="Поиск..."
        @input="onSearch"
      />
      <button v-if="searchQuery" @click="clearSearch" class="clear-button">✕</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SearchBar',
  data() {
    return {
      searchQuery: ''
    }
  },
  methods: {
    onSearch() {
      this.$emit('search', this.searchQuery)
    },
    clearSearch() {
      this.searchQuery = ''
      this.$emit('search', '')
    }
  }
}
</script>

<style scoped>
.search-bar {
  padding: 12px 16px;
  background: var(--tg-theme-bg-color, #ffffff);
  position: sticky;
  top: 0;
  z-index: 100;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-radius: 12px;
  padding: 8px 12px;
}

.search-icon {
  font-size: 18px;
  margin-right: 8px;
  opacity: 0.6;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 16px;
  color: var(--tg-theme-text-color, #000000);
}

.search-input::placeholder {
  color: var(--tg-theme-hint-color, #999999);
}

.clear-button {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--tg-theme-hint-color, #999999);
  cursor: pointer;
  padding: 0 4px;
}
</style>
