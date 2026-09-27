import { createRouter, createWebHistory } from "vue-router";

function categoryRoutes(category, pathBase) {
  return [
    {
      path: pathBase,
      name: `${category}-list`,
      component: () => import("./pages/ItemListPage.vue"),
      props: () => ({ category }),
    },
    {
      path: `${pathBase}/:id`,
      name: `${category}-detail`,
      component: () => import("./pages/ItemDetailPage.vue"),
      props: (route) => ({ category, id: route.params.id }),
    },
  ];
}

const routes = [
  {
    path: "/",
    name: "dashboard",
    component: () => import("./pages/DashboardPage.vue"),
  },
  ...categoryRoutes("instrument", "/instrumente"),
  ...categoryRoutes("clothing", "/kleidung"),
  ...categoryRoutes("sheet_music", "/noten"),
  ...categoryRoutes("general_item", "/allgemein"),
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
    path: "/rechnungen",
    name: "invoices",
    component: () => import("./pages/InvoiceListPage.vue"),
  },
  {
    path: "/notenscanner",
    name: "scanner-projects",
    component: () => import("./pages/ScanProjectListPage.vue"),
  },
  {
    path: "/notenscanner/bibliothek",
    name: "symbol-library",
    component: () => import("./pages/SymbolLibraryPage.vue"),
  },
  {
    path: "/notenscanner/konfiguration",
    name: "scanner-config",
    component: () => import("./pages/ScannerConfigPage.vue"),
  },
  {
    path: "/notenscanner/:id",
    name: "scanner-project-detail",
    component: () => import("./pages/ScanProjectDetailPage.vue"),
    props: (route) => ({ id: route.params.id }),
  },
  {
    path: "/notenscanner/:id/scan/:scanId",
    name: "scan-analysis",
    component: () => import("./pages/ScanAnalysisPage.vue"),
    props: (route) => ({ projectId: route.params.id, scanId: route.params.scanId }),
  },
  {
    path: "/notenscanner/:id/scan/:scanId/editor",
    name: "scan-editor",
    component: () => import("./pages/LilypondEditorPage.vue"),
    props: (route) => ({ projectId: route.params.id, scanId: route.params.scanId }),
  },
  {
    path: "/import",
    name: "import-list",
    component: () => import("./pages/ImportListPage.vue"),
  },
  {
    path: "/import/:id",
    name: "import-session",
    component: () => import("./pages/ImportSessionPage.vue"),
    props: true,
  },
  {
    path: "/einstellungen/instrumententypen",
    name: "instrument-types",
    component: () => import("./pages/InstrumentTypeListPage.vue"),
  },
  {
    path: "/einstellungen/register",
    name: "registers",
    component: () => import("./pages/RegisterListPage.vue"),
  },
  {
    path: "/einstellungen/kleidungstypen",
    name: "clothing-types",
    component: () => import("./pages/ClothingTypeListPage.vue"),
  },
  {
    path: "/einstellungen/kategorien",
    name: "general-item-categories",
    component: () => import("./pages/GeneralItemCategoryListPage.vue"),
  },
  {
    path: "/einstellungen/notengenres",
    name: "sheet-music-genres",
    component: () => import("./pages/SheetMusicGenreListPage.vue"),
  },
  {
    path: "/einstellungen/waehrungen",
    name: "currencies",
    component: () => import("./pages/CurrencyListPage.vue"),
  },
  {
    path: "/einstellungen/zugriff",
    name: "access-settings",
    component: () => import("./pages/AccessSettingsPage.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_PATH || "/"),
  routes,
});

export default router;
