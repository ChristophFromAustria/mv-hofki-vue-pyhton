import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    name: "dashboard",
    component: () => import("./pages/DashboardPage.vue"),
  },
  {
    path: "/instrumente",
    name: "instruments",
    component: () => import("./pages/InstrumentListPage.vue"),
  },
  {
    path: "/instrumente/neu",
    name: "instrument-create",
    component: () => import("./pages/InstrumentFormPage.vue"),
  },
  {
    path: "/instrumente/:id",
    name: "instrument-detail",
    component: () => import("./pages/InstrumentDetailPage.vue"),
  },
  {
    path: "/instrumente/:id/bearbeiten",
    name: "instrument-edit",
    component: () => import("./pages/InstrumentFormPage.vue"),
  },
  {
    path: "/musiker",
    name: "musicians",
    component: () => import("./pages/MusicianListPage.vue"),
  },
  {
    path: "/musiker/neu",
    name: "musician-create",
    component: () => import("./pages/MusicianFormPage.vue"),
  },
  {
    path: "/musiker/:id",
    name: "musician-detail",
    component: () => import("./pages/MusicianDetailPage.vue"),
  },
  {
    path: "/musiker/:id/bearbeiten",
    name: "musician-edit",
    component: () => import("./pages/MusicianFormPage.vue"),
  },
  {
    path: "/leihen",
    name: "loans",
    component: () => import("./pages/LoanListPage.vue"),
  },
  {
    path: "/einstellungen/instrumententypen",
    name: "instrument-types",
    component: () => import("./pages/InstrumentTypeListPage.vue"),
  },
  {
    path: "/einstellungen/waehrungen",
    name: "currencies",
    component: () => import("./pages/CurrencyListPage.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_PATH || "/"),
  routes,
});

export default router;
