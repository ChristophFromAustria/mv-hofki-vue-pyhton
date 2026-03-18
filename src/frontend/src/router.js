import { createRouter, createWebHistory } from "vue-router";
import HomePage from "./pages/HomePage.vue";

const routes = [
  {
    path: "/",
    name: "home",
    component: HomePage,
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_PATH || "/"),
  routes,
});

// Placeholder for auth route guard:
// router.beforeEach((to, from, next) => {
//   // Check auth state, redirect to login if needed
//   next();
// });

export default router;
