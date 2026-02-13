<template>
  <div class="card mentor-card" @click="$emit('click', mentor)">
    <div class="mentor-header">
      <div class="mentor-avatar">{{ mentor.avatar }}</div>
      <div class="mentor-info">
        <h3 class="card-title">{{ mentor.name }}</h3>
        <span class="specialty">{{ mentor.specialty }}</span>
        <div class="mentor-meta">
          <span class="rating">⭐ {{ mentor.rating }}</span>
          <span class="experience">{{ mentor.experience }}</span>
        </div>
      </div>
    </div>
    <div class="card-tags">
      <span v-for="tag in mentor.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
    <div class="price">{{ mentor.price }}</div>
  </div>
</template>

<script>
export default {
  name: 'MentorCard',
  props: {
    mentor: {
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

.mentor-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.mentor-avatar {
  font-size: 48px;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  border-radius: 50%;
  flex-shrink: 0;
}

.mentor-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--tg-theme-text-color, #000000);
  margin: 0;
}

.specialty {
  font-size: 14px;
  color: var(--tg-theme-hint-color, #999999);
}

.mentor-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  margin-top: 4px;
}

.rating {
  color: var(--tg-theme-text-color, #000000);
  font-weight: 600;
}

.experience {
  color: var(--tg-theme-hint-color, #999999);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag {
  font-size: 12px;
  padding: 4px 10px;
  background: var(--tg-theme-secondary-bg-color, #f0f0f0);
  color: var(--tg-theme-text-color, #000000);
  border-radius: 12px;
}

.price {
  font-size: 16px;
  font-weight: 600;
  color: var(--tg-theme-button-color, #3390ec);
  text-align: right;
}
</style>
