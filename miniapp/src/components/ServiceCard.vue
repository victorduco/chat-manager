<template>
  <div class="card service-card" @click="$emit('click', service)">
    <div class="card-header">
      <h3 class="card-title">{{ service.title }}</h3>
      <span class="provider">{{ service.provider }}</span>
    </div>
    <div class="service-info">
      <div class="info-row">
        <span class="info-item">⏱ {{ service.duration }}</span>
        <span class="rating">⭐ {{ service.rating }}</span>
      </div>
      <div class="price">{{ service.price }}</div>
    </div>
    <div class="card-tags">
      <span v-for="tag in service.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ServiceCard',
  props: {
    service: {
      type: Object,
      required: true
    }
  }
}
</script>

<style scoped>
.card {
  background: var(--tg-theme-bg-color, #ffffff);
  border-radius: 12px;
  padding: 16px;
  margin: 8px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:active {
  transform: scale(0.98);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.card-header {
  margin-bottom: 12px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
  margin: 0 0 4px 0;
}

.provider {
  font-size: 14px;
  color: var(--tg-theme-hint-color, #999999);
}

.service-info {
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.info-item {
  font-size: 14px;
  color: var(--tg-theme-text-color, #000000);
}

.rating {
  font-size: 14px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
}

.price {
  font-size: 16px;
  font-weight: 600;
  color: var(--tg-theme-button-color, #3390ec);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  font-size: 12px;
  padding: 4px 10px;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  color: var(--tg-theme-text-color, #000000);
  border-radius: 12px;
}
</style>
