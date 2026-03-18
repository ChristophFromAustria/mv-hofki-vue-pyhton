<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  images: { type: Array, default: () => [] },
  canUpload: { type: Boolean, default: false },
  canManage: { type: Boolean, default: false },
});

const emit = defineEmits(["upload", "set-profile", "delete"]);

const currentIndex = ref(0);
const showModal = ref(false);

const current = computed(() => props.images[currentIndex.value]);

function prev() {
  if (currentIndex.value > 0) currentIndex.value--;
}
function next() {
  if (currentIndex.value < props.images.length - 1) currentIndex.value++;
}

function openModal() {
  if (current.value) showModal.value = true;
}

const fileInput = ref(null);
function triggerUpload() {
  fileInput.value?.click();
}
function onFileSelected(e) {
  const file = e.target.files?.[0];
  if (file) emit("upload", file);
  e.target.value = "";
}
</script>

<template>
  <div class="gallery">
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      style="display: none"
      @change="onFileSelected"
    />

    <!-- No images placeholder -->
    <div v-if="!images.length" class="gallery-placeholder" @click="canUpload && triggerUpload()">
      <div class="gallery-plus" :style="{ cursor: canUpload ? 'pointer' : 'default' }">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span v-if="canUpload">Bild hinzufügen</span>
      </div>
    </div>

    <!-- Gallery with images -->
    <template v-else>
      <div class="gallery-main" @click="openModal">
        <button v-if="images.length > 1" class="gallery-nav gallery-nav-left" @click.stop="prev">
          &#8249;
        </button>
        <img :src="current.url" :alt="`Bild ${currentIndex + 1}`" class="gallery-img" />
        <button v-if="images.length > 1" class="gallery-nav gallery-nav-right" @click.stop="next">
          &#8250;
        </button>
        <div class="gallery-counter">{{ currentIndex + 1 }} / {{ images.length }}</div>
      </div>

      <div v-if="canManage || canUpload" class="gallery-actions">
        <button v-if="canUpload" class="btn-sm" @click="triggerUpload">Bild hinzufügen</button>
        <button
          v-if="canManage && current && !current.is_profile"
          class="btn-sm"
          @click="$emit('set-profile', current.id)"
        >
          Als Profilbild
        </button>
        <span v-if="canManage && current?.is_profile" class="badge badge-green">Profilbild</span>
        <button
          v-if="canManage && current"
          class="btn-sm btn-danger"
          @click="$emit('delete', current.id)"
        >
          Löschen
        </button>
      </div>

      <!-- Thumbnail strip -->
      <div v-if="images.length > 1" class="gallery-thumbs">
        <img
          v-for="(img, i) in images"
          :key="img.id"
          :src="img.url"
          :class="{ active: i === currentIndex }"
          class="gallery-thumb"
          @click="currentIndex = i"
        />
      </div>
    </template>

    <!-- Modal -->
    <div v-if="showModal" class="overlay" @click="showModal = false">
      <div class="gallery-modal" @click.stop>
        <button class="gallery-modal-close" @click="showModal = false">&times;</button>
        <button v-if="images.length > 1" class="gallery-modal-nav left" @click="prev">
          &#8249;
        </button>
        <img :src="current.url" :alt="`Bild ${currentIndex + 1}`" />
        <button v-if="images.length > 1" class="gallery-modal-nav right" @click="next">
          &#8250;
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gallery-placeholder {
  background: var(--color-bg-soft);
  border: 2px dashed var(--color-border);
  border-radius: 8px;
  padding: 3rem;
  text-align: center;
  color: var(--color-muted);
}

.gallery-plus {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.gallery-main {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  background: var(--color-bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  max-height: 400px;
}

.gallery-img {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
  display: block;
}

.gallery-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  font-size: 1.5rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0.8;
  padding: 0;
}

.gallery-nav:hover {
  opacity: 1;
}

.gallery-nav-left {
  left: 8px;
}
.gallery-nav-right {
  right: 8px;
}

.gallery-counter {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.gallery-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-top: 0.5rem;
}

.gallery-thumbs {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  overflow-x: auto;
}

.gallery-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 2px solid transparent;
  cursor: pointer;
  opacity: 0.6;
}

.gallery-thumb.active {
  border-color: var(--color-primary);
  opacity: 1;
}

.gallery-modal {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.gallery-modal img {
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
}

.gallery-modal-close {
  position: absolute;
  top: -12px;
  right: -12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  width: 32px;
  height: 32px;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  padding: 0;
}

.gallery-modal-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.8);
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  font-size: 2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.gallery-modal-nav.left {
  left: 12px;
}
.gallery-modal-nav.right {
  right: 12px;
}
</style>
