const requestedPlatform = new URLSearchParams(window.location.search).get("platform");
const isWindowsPlatform = requestedPlatform === "windows" || /Windows/i.test(String(navigator.userAgent || ""));
document.documentElement.classList.toggle("platform-windows", isWindowsPlatform);
const INTERNAL_EDITOR_NAV_KEY = "grokStudioInternalEditorNavigation";
const IMAGE_EDITOR_SAVED_KEY = "grokStudioImageEditorSavedItemId";
const IMAGE_EDITOR_RETURN_CONTEXT_KEY = "grokStudioImageEditorReturnContext";
const VIDEO_MODEL_15 = "grok-imagine-video-1.5";
const VIDEO_MODEL_15_PREVIEW = "grok-imagine-video-1.5-preview";
const savedVideoModel = localStorage.getItem("grokStudioVideoModel");
const IMAGINE_REMOTE_PAGE_SIZE = 15;
const IMAGINE_REMOTE_VIEW_ALL = "all";
const IMAGINE_REMOTE_VIEW_DISCOVER = "discover";
const IMAGINE_REMOTE_VIEW_ALL_FILES = "all_files";
const IMAGINE_MEDIA_TYPE_ALL = "all";
const IMAGINE_MEDIA_TYPE_VIDEO = "video";
const IMAGINE_MEDIA_TYPE_IMAGE = "image";
const IMAGINE_PORTFOLIO_TYPE_ALL = IMAGINE_MEDIA_TYPE_ALL;
const IMAGINE_PORTFOLIO_TYPE_VIDEO = IMAGINE_MEDIA_TYPE_VIDEO;
const IMAGINE_PORTFOLIO_TYPE_IMAGE = IMAGINE_MEDIA_TYPE_IMAGE;
const IMAGINE_DISCOVER_TYPE_ALL = IMAGINE_MEDIA_TYPE_ALL;
const IMAGINE_DISCOVER_TYPE_VIDEO = IMAGINE_MEDIA_TYPE_VIDEO;
const IMAGINE_DISCOVER_TYPE_IMAGE = IMAGINE_MEDIA_TYPE_IMAGE;
const IMAGINE_ALL_FILES_TYPE_ALL = IMAGINE_MEDIA_TYPE_ALL;
const IMAGINE_ALL_FILES_TYPE_VIDEO = IMAGINE_MEDIA_TYPE_VIDEO;
const IMAGINE_ALL_FILES_TYPE_IMAGE = IMAGINE_MEDIA_TYPE_IMAGE;
const IMAGINE_ALL_FILES_TYPE_FILL_MAX_PAGES = 6;
const UPLOAD_HISTORY_PAGE_SIZE = 18;
const ACCOUNT_TIERS = ["free", "super", "heavy"];
const ACCOUNT_TIER_LABELS = {
  free: "Free",
  super: "Super",
  heavy: "Heavy",
};

const state = {
  items: [],
  categories: [],
  galleryFolders: [],
  jobs: [],
  uploads: [],
  auth: null,
  accounts: [],
  imagine: null,
  imagineAccounts: [],
  generationProvider: "build",
  cliAuthFile: "",
  filter: "all",
  workspaceFolderId: "",
  selectedPrimaryFolderId: "",
  selectedSecondaryFolderId: "",
  galleryCollectionSelected: true,
  gallerySort: "",
  gallerySavedSort: "",
  galleryDraftLayout: null,
  mode: "image",
  selectedVideoId: "",
  notifiedJobs: new Set(),
  sidebarCollapsed: localStorage.getItem("grokStudioSidebarCollapsed") === "1",
  selectedItems: new Set(),
  view: "gallery",
  detailItemId: "",
  detailNavView: "gallery",
  detailNavFilter: "all",
  detailSelectedSourceUrl: "",
  detailSelectedJobId: "",
  detailThumbScrollTop: 0,
  detailExtend: false,
  detailExtendStart: 0,
  detailExtendComposerGuardUntil: 0,
  detailExtendComposerGestureActive: false,
  library: null,
  editImages: [],
  referenceImages: [],
  startImage: null,
  sourceVideo: null,
  attachmentTrayOpen: false,
  uploadHistoryVisibleCount: UPLOAD_HISTORY_PAGE_SIZE,
  previewOverlay: null,
  promptEditorOverlay: null,
  libraryFolderOverlay: null,
  moveToGalleryOverlay: null,
  galleryActionOverlay: null,
  accountScreenVisible: false,
  accountHistoryOpen: false,
  accountDrag: null,
  imagineAccountStatuses: {},
  imagineAccountStatusToken: 0,
  imagineRemoteView: IMAGINE_REMOTE_VIEW_ALL,
  imaginePortfolioTypeFilter: IMAGINE_PORTFOLIO_TYPE_ALL,
  imagineDiscoverTypeFilter: IMAGINE_DISCOVER_TYPE_ALL,
  imagineAllFilesTypeFilter: IMAGINE_ALL_FILES_TYPE_ALL,
  imagineRemoteItems: [],
  imagineRemoteCursor: "",
  imagineRemoteAccountKey: "",
  imagineRemoteCaches: new Map(),
  imagineRemoteBusy: false,
  imagineRemoteComplete: false,
  imagineRemoteLoadedOnce: false,
  imagineRemoteSuppressAutoLoadUntil: 0,
  imagineRemoteRenderSignature: "",
  imagineRemoteToken: 0,
  imagineAllFilesClassified: false,
  imagineAllFilesClassifyBusy: false,
  imagineAllFilesClassifyToken: 0,
  imaginePortfolioTypeFillToken: 0,
  imagineDiscoverTypeFillToken: 0,
  imagineAllFilesTypeFillToken: 0,
  videoModel: savedVideoModel === null ? VIDEO_MODEL_15 : savedVideoModel,
  imageModel: localStorage.getItem("grokStudioImageModel") || "grok-imagine-image",
  durationMode: "",
  resolutionMode: "",
  lastErrorText: "",
  shutdownSent: false,
  promptExpanded: false,
  postJobRefreshTimers: new Map(),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const els = {
  appShell: $("#appShell"),
  sidebarOpenBtn: $("#sidebarOpenBtn"),
  sidebarCloseBtn: $("#sidebarCloseBtn"),
  brandHomeBtn: $("#brandHomeBtn"),
  titleHomeBtn: $("#titleHomeBtn"),
  workspaceContext: $("#workspaceContext"),
  galleryNavBtn: $("#galleryNavBtn"),
  imagineNavBtn: $("#imagineNavBtn"),
  folderGalleryScreen: $("#folderGalleryScreen"),
  imagineLibraryScreen: $("#imagineLibraryScreen"),
  imagineGallery: $("#imagineGallery"),
  workspaceMediaTypeFilters: $("#workspaceMediaTypeFilters"),
  imagineAllViewBtn: $("#imagineAllViewBtn"),
  imagineDiscoverViewBtn: $("#imagineDiscoverViewBtn"),
  imagineAllFilesViewBtn: $("#imagineAllFilesViewBtn"),
  imagineMediaTypeFilters: $("#imagineMediaTypeFilters"),
  imagineImportBtn: $("#imagineImportBtn"),
  makeFolderBtn: $("#makeFolderBtn"),
  renameFolderBtn: $("#renameFolderBtn"),
  deleteFolderBtn: $("#deleteFolderBtn"),
  saveGallerySortBtn: $("#saveGallerySortBtn"),
  collectionHeadingBtn: $("#collectionHeadingBtn"),
  primaryFolderList: $("#primaryFolderList"),
  secondaryFolderGrid: $("#secondaryFolderGrid"),
  secondaryFolderTitle: $("#secondaryFolderTitle"),
  categoryInput: $("#categoryInput"),
  searchInput: $("#searchInput"),
  sidebarSearchLabel: $(".sidebar-search-label"),
  refreshBtn: $("#refreshBtn"),
  promptInput: $("#promptInput"),
  tagsInput: $("#tagsInput"),
  countInput: $("#countInput"),
  durationInput: $("#durationInput"),
  trimQualityInput: $("#trimQualityInput"),
  aspectInput: $("#aspectInput"),
  imageModelInput: $("#imageModelInput"),
  resolutionInput: $("#resolutionInput"),
  videoModelInput: $("#videoModelInput"),
  analyzeModelInput: $("#analyzeModelInput"),
  submitBtn: $("#submitBtn"),
  savePromptBtn: $("#savePromptBtn"),
  imageFiles: $("#imageFiles"),
  imageSourceDrop: $("#imageSourceDrop"),
  startImageDrop: $("#startImageDrop"),
  startImageFile: $("#startImageFile"),
  startImagePreview: $("#startImagePreview"),
  referenceImageDrop: $("#referenceImageDrop"),
  referenceImageFiles: $("#referenceImageFiles"),
  sourceVideoDrop: $("#sourceVideoDrop"),
  sourceVideoFile: $("#sourceVideoFile"),
  sourceVideoSelect: $("#sourceVideoSelect"),
  sourceVideoPreview: $("#sourceVideoPreview"),
  imageFileNames: $("#imageFileNames"),
  videoFileNames: $("#videoFileNames"),
  jobSummary: $("#jobSummary"),
  jobList: $("#jobList"),
  gallery: $("#gallery"),
  libraryCount: $("#libraryCount"),
  promptNewBtn: $("#promptNewBtn"),
  downloadSelectedBtn: $("#downloadSelectedBtn"),
  moveToGalleryBtn: $("#moveToGalleryBtn"),
  deleteSelectedBtn: $("#deleteSelectedBtn"),
  libraryActions: $(".library-actions"),
  librarySelectionClearBtn: $("#librarySelectionClearBtn"),
  openFolderTitle: $("#openFolderTitle"),
  accountButton: $("#accountButton"),
  accountAvatar: $("#accountAvatar"),
  usagePageBtn: $("#usagePageBtn"),
  accountEmail: $("#accountEmail"),
  accountOverlay: $("#accountOverlay"),
  accountScreen: $("#accountScreen"),
  accountNameInput: $("#accountNameInput"),
  accountPathInput: $("#accountPathInput"),
  registerAccountBtn: $("#registerAccountBtn"),
  accountList: $("#accountList"),
  imagineLoginBtn: $("#imagineLoginBtn"),
  imagineCaptureBtn: $("#imagineCaptureBtn"),
  imagineLogoutBtn: $("#imagineLogoutBtn"),
  modelToggleButtons: $$(".model-toggle"),
  studioFullscreenPlayer: $("#studioFullscreenPlayer"),
  errorPanel: $("#errorPanel"),
  errorTitle: $("#errorTitle"),
  errorKind: $("#errorKind"),
  errorBody: $("#errorBody"),
  copyErrorBtn: $("#copyErrorBtn"),
  closeErrorBtn: $("#closeErrorBtn"),
  toast: $("#toast"),
  libraryFolderBtn: $("#libraryFolderBtn"),
  setLibraryPathBtn: $("#setLibraryPathBtn"),
  libraryFolderPath: $("#libraryFolderPath"),
  selectionBar: $("#selectionBar"),
  selectionCount: $("#selectionCount"),
  selectionDownloadBtn: $("#selectionDownloadBtn"),
  selectionDeleteBtn: $("#selectionDeleteBtn"),
  selectionClearBtn: $("#selectionClearBtn"),
  detailScreen: $("#detailScreen"),
  composerAttachBtn: $("#composerAttachBtn"),
  attachmentTray: $("#attachmentTray"),
  uploadHistoryStrip: $("#uploadHistoryStrip"),
};

function toast(message, kind = "info") {
  if (kind !== "error") return;
  els.toast.textContent = message;
  els.toast.dataset.kind = kind;
  els.toast.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    els.toast.hidden = true;
  }, 4200);
}

function toastError(message) {
  toast(message, "error");
}

async function copyText(text) {
  const value = String(text || "");
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the click-driven fallback for non-secure local network URLs.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, value.length);
  try {
    return document.execCommand("copy");
  } finally {
    textarea.remove();
  }
}

function showErrorPanel(title, message) {
  const text = String(message || "Unknown error");
  state.lastErrorText = text;
  hideErrorPanel();
  toastError(errorToastMessage(text));
}

function hideErrorPanel() {
  els.errorPanel.hidden = true;
}

function errorKind(message) {
  const text = String(message || "").toLowerCase();
  if (isModerationError(text)) return "Moderate";
  if (isCreditLimitError(text)) return "Credit Limit";
  if (text.includes("oauth") || text.includes("bad-credentials") || text.includes("401") || text.includes("403")) return "Auth";
  if (text.includes("cancelled")) return "Cancelled";
  return "Error";
}

function isModerationError(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("content_policy_violation")
    || text.includes("moderation")
    || text.includes("moderate");
}

function isCreditLimitError(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("run out of credits")
    || text.includes("out of credits")
    || text.includes("credit limit")
    || text.includes("spending-limit")
    || text.includes("spending limit")
    || text.includes("need a grok subscription")
    || text.includes("upgrade at")
    || text.includes("credits or need");
}

function moderationToastMessage() {
  return "Moderated";
}

function errorToastMessage(message) {
  const text = String(message || "Unknown error").trim();
  if (isModerationError(text)) return moderationToastMessage();
  if (isCreditLimitError(text)) return "Credit Limit";

  const jsonStart = text.indexOf("{");
  const jsonEnd = text.lastIndexOf("}");
  if (jsonStart >= 0 && jsonEnd > jsonStart) {
    try {
      const payload = JSON.parse(text.slice(jsonStart, jsonEnd + 1));
      const payloadError = payload?.error;
      const summary = typeof payloadError === "string"
        ? payloadError
        : payloadError?.message || payload?.message || payload?.detail;
      if (summary) return String(summary).trim().slice(0, 240);
    } catch {
      // Fall back to the first readable line when an API response is not valid JSON.
    }
  }

  const readable = text
    .replace(/^xAI API error HTTP \d+:\s*/i, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && line !== "{" && line !== "}");
  return (readable || "Unknown error").slice(0, 240);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function reportClientEvent(event, detail = {}) {
  const body = JSON.stringify({ event, detail, mode: state.mode, at: new Date().toISOString() });
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/api/client-event", blob);
      return;
    }
  } catch (error) {
    console.warn(error);
  }
  fetch("/api/client-event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {});
}

async function loadState(options = {}) {
  const data = await api("/api/state");
  state.items = data.items || [];
  state.categories = data.categories || [];
  state.galleryFolders = data.gallery_folders || [];
  state.gallerySavedSort = data.gallery_sort || "";
  if (options.resetGallerySort || state.view !== "folder-gallery") {
    state.gallerySort = state.gallerySavedSort;
    state.galleryDraftLayout = null;
  }
  state.jobs = data.jobs || [];
  state.uploads = data.uploads || [];
  state.auth = data.auth || null;
  state.imagine = data.imagine || null;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts || [];
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  state.library = data.library || null;
  state.cliAuthFile = data.cli_auth_file || state.auth?.auth_file || "";
  renderAuth(data.auth);
  renderImagineAccount();
  renderLibraryFolderPath();
  renderCategories();
  renderVideoChoices();
  renderJobs();
  renderGallery();
  renderFolderGallery();
  syncWorkspaceView();
  const requestedDetailId = new URL(window.location.href).searchParams.get("detail") || "";
  const requestedDetailNavContext = requestedDetailId
    ? takeImageEditorReturnContext() || detailNavContextFromHistory(history.state)
    : null;
  if (requestedDetailId) {
    if (galleryItemById(requestedDetailId)) {
      if (state.view !== "detail" || state.detailItemId !== requestedDetailId) {
        openDetail(requestedDetailId, { fromHistory: true, navContext: requestedDetailNavContext });
      } else {
        if (requestedDetailNavContext) setDetailNavContext(requestedDetailNavContext);
        syncWorkspaceView();
        renderDetail();
      }
    } else {
      state.view = "gallery";
      state.detailItemId = "";
      state.detailNavView = "gallery";
      state.detailNavFilter = state.filter;
      state.detailSelectedSourceUrl = "";
      state.detailSelectedJobId = "";
      history.replaceState(
        { ...history.state, grokStudioView: "gallery", detailItemId: "", workspaceFolderId: state.workspaceFolderId },
        "",
        detailHistoryUrl(),
      );
      syncWorkspaceView();
      renderDetail();
    }
  } else {
    renderDetail();
  }
  if (state.view === "imagine-library") renderImagineLibrary();
  renderAttachmentTray();
  maybePrefetchImagineRemoteLibrary();
}

function renderAuth(auth) {
  document.title = auth?.active ? "Grok Studio Lab" : "Grok Studio Lab - OAuth expired";
  if (!hasAnyVisibleAccount(auth)) {
    if (els.accountAvatar) els.accountAvatar.textContent = "A";
    if (els.accountEmail) els.accountEmail.textContent = "Account";
    if (els.accountPathInput && !els.accountPathInput.value && (state.cliAuthFile || auth?.auth_file)) {
      els.accountPathInput.value = state.cliAuthFile || auth.auth_file;
    }
    return;
  }
  const provider = state.generationProvider === "imagine" ? "imagine" : "build";
  const label = provider === "imagine"
    ? imagineAccountLabel()
    : buildAccountLabel(auth);
  if (els.accountAvatar) els.accountAvatar.textContent = provider === "imagine" ? "I" : "B";
  if (els.accountEmail) els.accountEmail.textContent = label;
  if (els.accountPathInput && !els.accountPathInput.value && (state.cliAuthFile || auth?.auth_file)) {
    els.accountPathInput.value = state.cliAuthFile || auth.auth_file;
  }
}

function hasAnyVisibleAccount(auth = state.auth) {
  const hasBuild = Boolean(auth?.email)
    || state.accounts.some((account) => account?.exists !== false && Boolean(account.email || account.label));
  const hasImagine = Boolean(state.imagine?.connected || state.imagine?.email || state.imagine?.label)
    || state.imagineAccounts.some((account) => Boolean(account.email || account.label));
  return hasBuild || hasImagine;
}

function buildAccountLabel(auth = state.auth) {
  return auth?.email || state.accounts.find((account) => account.selected)?.email || "Build";
}

function imagineAccountLabel() {
  return state.imagine?.email || state.imagine?.label || "Imagine";
}

function renderLibraryFolderPath() {
  if (!els.libraryFolderPath) return;
  const root = state.library?.external
    ? state.library.root
    : (state.library?.default_folder_path || "");
  els.libraryFolderPath.textContent = root || "No folder selected";
  els.libraryFolderPath.title = root || "";
}

function galleryFolderById(id) {
  return state.galleryFolders.find((folder) => folder.id === id) || null;
}

function primaryGalleryFolders() {
  return state.galleryFolders
    .filter((folder) => !folder.parent_id)
    .sort((a, b) => (
      Number(a.order ?? Number.MAX_SAFE_INTEGER) - Number(b.order ?? Number.MAX_SAFE_INTEGER)
      || String(a.created_at || "").localeCompare(String(b.created_at || ""))
    ));
}

function secondaryGalleryFolders(parentId) {
  const folders = state.galleryFolders
    .filter((folder) => folder.parent_id === parentId)
    .sort((a, b) => (
      Number(a.grid_slot ?? Number.MAX_SAFE_INTEGER) - Number(b.grid_slot ?? Number.MAX_SAFE_INTEGER)
      || Number(a.order ?? Number.MAX_SAFE_INTEGER) - Number(b.order ?? Number.MAX_SAFE_INTEGER)
      || String(a.created_at || "").localeCompare(String(b.created_at || ""))
    ));
  const occupied = new Set();
  let nextSlot = 0;
  folders.forEach((folder) => {
    let slot = Number(folder.grid_slot);
    if (!Number.isInteger(slot) || slot < 0 || occupied.has(slot)) {
      while (occupied.has(nextSlot)) nextSlot += 1;
      slot = nextSlot;
      folder.grid_slot = slot;
    }
    occupied.add(slot);
    nextSlot = Math.max(nextSlot, slot + 1);
  });
  const draft = state.galleryDraftLayout?.parentId === parentId
    ? state.galleryDraftLayout.slots
    : null;
  return folders
    .map((folder) => (
      draft && Object.hasOwn(draft, folder.id)
        ? { ...folder, grid_slot: draft[folder.id] }
        : folder
    ))
    .sort((a, b) => Number(a.grid_slot) - Number(b.grid_slot));
}

async function saveGalleryFolderLayout(entries, options = {}) {
  if (!entries.length && !Object.hasOwn(options, "sortMode")) return;
  const body = { folders: entries };
  if (Object.hasOwn(options, "sortMode")) body.sort_mode = options.sortMode;
  const data = await api("/api/gallery/folders/layout", {
    method: "POST",
    body: JSON.stringify(body),
  });
  state.galleryFolders = data.gallery_folders || state.galleryFolders;
  if (Object.hasOwn(data, "gallery_sort")) state.gallerySavedSort = data.gallery_sort || "";
}

async function sortSecondaryGalleryFolders(mode) {
  const parentId = state.selectedPrimaryFolderId;
  if (!parentId) {
    toastError("Select a collection.");
    return;
  }
  const locale = mode === "ko" ? "ko-KR" : "en-US";
  const folders = secondaryGalleryFolders(parentId)
    .slice()
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), locale, { numeric: true }));
  state.gallerySort = mode;
  document.querySelectorAll("[data-gallery-sort]").forEach((button) => {
    button.classList.toggle("active", button.dataset.gallerySort === mode);
  });
  state.galleryDraftLayout = {
    parentId,
    slots: Object.fromEntries(folders.map((folder, index) => [folder.id, index])),
  };
  renderFolderGallery();
}

async function saveCurrentGallerySort() {
  const parentId = state.selectedPrimaryFolderId;
  const entries = parentId
    ? secondaryGalleryFolders(parentId).map((folder, index) => ({
      id: folder.id,
      order: index,
      grid_slot: Number(folder.grid_slot) || 0,
    }))
    : [];
  await saveGalleryFolderLayout(entries, { sortMode: state.gallerySort });
  state.gallerySort = state.gallerySavedSort;
  state.galleryDraftLayout = null;
  renderFolderGallery();
}

async function reorderPrimaryFolder(draggedId, targetId) {
  if (!draggedId || !targetId || draggedId === targetId) return;
  const folders = primaryGalleryFolders();
  const draggedIndex = folders.findIndex((folder) => folder.id === draggedId);
  const targetIndex = folders.findIndex((folder) => folder.id === targetId);
  if (draggedIndex < 0 || targetIndex < 0) return;
  const [dragged] = folders.splice(draggedIndex, 1);
  folders.splice(targetIndex, 0, dragged);
  await saveGalleryFolderLayout(folders.map((folder, index) => ({ id: folder.id, order: index })));
  renderFolderGallery();
}

async function moveSecondaryFolderToSlot(folderId, rawSlot) {
  const folder = galleryFolderById(folderId);
  if (!folder?.parent_id) return;
  const slot = Math.max(0, Number(rawSlot) || 0);
  const siblings = secondaryGalleryFolders(folder.parent_id);
  const displayedFolder = siblings.find((candidate) => candidate.id === folderId);
  const occupied = siblings.find((candidate) => candidate.id !== folderId && Number(candidate.grid_slot) === slot);
  const oldSlot = Math.max(0, Number(displayedFolder?.grid_slot ?? folder.grid_slot) || 0);
  const entries = [{ id: folderId, grid_slot: slot }];
  if (occupied) entries.push({ id: occupied.id, grid_slot: oldSlot });
  await saveGalleryFolderLayout(entries);
  state.gallerySort = "";
  state.galleryDraftLayout = null;
  document.querySelectorAll("[data-gallery-sort]").forEach((button) => button.classList.remove("active"));
  renderFolderGallery();
}

function workspaceFolder() {
  return galleryFolderById(state.workspaceFolderId);
}

function workspaceFolderLabel() {
  const secondary = workspaceFolder();
  if (!secondary) return "";
  const primary = galleryFolderById(secondary.parent_id);
  return [primary?.name, secondary.name].filter(Boolean).join(" / ");
}

function itemGalleryFolderId(item) {
  return String(item?.metadata?.gallery_folder_id || "");
}

function workspaceItems() {
  if (!state.workspaceFolderId) return state.items;
  return state.items.filter((item) => itemGalleryFolderId(item) === state.workspaceFolderId);
}

function workspaceJobs() {
  if (!state.workspaceFolderId) return state.jobs;
  return state.jobs.filter((job) => String(jobContext(job).gallery_folder_id || "") === state.workspaceFolderId);
}

function normalizeDetailNavView(view) {
  return ["folder-gallery", "imagine-library"].includes(view) ? view : "gallery";
}

function normalizeGalleryFilter(filter) {
  return ["all", "video", "image", "prompt"].includes(filter) ? filter : "all";
}

function normalizeDetailNavContext(context = {}) {
  return {
    view: normalizeDetailNavView(context.view),
    filter: normalizeGalleryFilter(context.filter || state.filter),
  };
}

function detailNavContextFromCurrentView() {
  if (state.view === "detail") {
    return normalizeDetailNavContext({
      view: state.detailNavView,
      filter: state.detailNavFilter,
    });
  }
  return normalizeDetailNavContext({
    view: state.view,
    filter: state.filter,
  });
}

function detailNavContextFromHistory(historyState = history.state) {
  if (!historyState) return null;
  if (!historyState.detailNavView && !historyState.detailNavFilter && !historyState.galleryFilter) return null;
  return normalizeDetailNavContext({
    view: historyState.detailNavView,
    filter: historyState.detailNavFilter || historyState.galleryFilter,
  });
}

function setDetailNavContext(context = {}) {
  const next = normalizeDetailNavContext(context);
  state.detailNavView = next.view;
  state.detailNavFilter = next.filter;
  return next;
}

function rememberImageEditorReturnContext() {
  try {
    sessionStorage.setItem(IMAGE_EDITOR_RETURN_CONTEXT_KEY, JSON.stringify(detailNavContextFromCurrentView()));
  } catch (error) {
    console.warn(error);
  }
}

function takeImageEditorReturnContext() {
  const raw = sessionStorage.getItem(IMAGE_EDITOR_RETURN_CONTEXT_KEY) || "";
  if (!raw) return null;
  sessionStorage.removeItem(IMAGE_EDITOR_RETURN_CONTEXT_KEY);
  try {
    return normalizeDetailNavContext(JSON.parse(raw));
  } catch {
    return null;
  }
}

function syncWorkspaceView() {
  const folderGalleryVisible = state.view === "folder-gallery";
  const imagineLibraryVisible = state.view === "imagine-library";
  const navContext = state.view === "detail" ? detailNavContextFromCurrentView() : null;
  const activeFilter = navContext?.filter || state.filter;
  const secondaryWorkspaceActive = Boolean(state.workspaceFolderId)
    && !folderGalleryVisible
    && !imagineLibraryVisible
    && ["all", "video", "image"].includes(activeFilter)
    && (state.view === "gallery" || navContext?.view === "gallery");
  const galleryNavActive = folderGalleryVisible || navContext?.view === "folder-gallery" || secondaryWorkspaceActive;
  const imagineLibraryActive = imagineLibraryVisible || navContext?.view === "imagine-library";
  document.querySelector(".workspace")?.classList.toggle("show-folder-gallery", folderGalleryVisible);
  document.querySelector(".workspace")?.classList.toggle("show-imagine-library", imagineLibraryVisible);
  if (els.folderGalleryScreen) els.folderGalleryScreen.hidden = !folderGalleryVisible;
  if (els.imagineLibraryScreen) els.imagineLibraryScreen.hidden = !imagineLibraryVisible;
  const label = workspaceFolderLabel();
  if (els.workspaceContext) {
    const showWorkspaceContext = Boolean(label)
      && !folderGalleryVisible
      && !imagineLibraryVisible
      && ["all", "video", "image"].includes(state.filter)
      && !els.searchInput?.value.trim();
    els.workspaceContext.hidden = !showWorkspaceContext;
    els.workspaceContext.textContent = showWorkspaceContext ? label : "";
  }
  $$(".nav-item").forEach((item) => {
    if (item === els.galleryNavBtn) {
      item.classList.toggle("active", galleryNavActive);
    } else if (item === els.imagineNavBtn) {
      item.classList.toggle("active", imagineLibraryActive);
    } else if (item.dataset.filter) {
      item.classList.toggle("active", !galleryNavActive && !imagineLibraryActive && item.dataset.filter === activeFilter);
    }
  });
}

function resetWorkspaceComposer() {
  if (state.view === "detail") closeDetail({ fromHistory: true });
  resetComposerAfterDetail();
  state.selectedItems.clear();
  state.filter = "all";
  if (els.searchInput) els.searchInput.value = "";
}

function openPrimaryHome(options = {}) {
  if (state.accountScreenVisible) showAccountScreen(false);
  resetWorkspaceComposer();
  state.workspaceFolderId = "";
  state.view = "gallery";
  syncWorkspaceView();
  renderGallery();
  if (!options.fromHistory) {
    history.pushState(
      { ...history.state, grokStudioView: "gallery", detailItemId: "", workspaceFolderId: "" },
      "",
      workspaceHistoryUrl(),
    );
  }
}

function openFolderGallery(options = {}) {
  if (state.accountScreenVisible) showAccountScreen(false);
  if (state.view === "detail") closeDetail({ fromHistory: true });
  state.view = "folder-gallery";
  state.gallerySort = state.gallerySavedSort;
  state.galleryDraftLayout = null;
  if (!state.selectedPrimaryFolderId) state.galleryCollectionSelected = true;
  state.selectedItems.clear();
  syncWorkspaceView();
  renderFolderGallery();
  if (!options.fromHistory) {
    history.pushState(
      { ...history.state, grokStudioView: "folder-gallery", detailItemId: "", workspaceFolderId: state.workspaceFolderId },
      "",
      workspaceHistoryUrl({ folderGallery: true }),
    );
  }
}

function renderImagineShell() {
  if (!els.imagineGallery) return;
  syncImagineViewButtons();
  els.imagineGallery.classList.add("gallery-empty");
  if (!els.imagineGallery.querySelector(".empty-state")) {
    els.imagineGallery.innerHTML = `<div class="empty-state">No Imagine item yet.</div>`;
  }
  if (els.imagineImportBtn) els.imagineImportBtn.textContent = "Selected Import";
}

function resetImagineLibraryScroll() {
  if (els.imagineGallery) els.imagineGallery.scrollTop = 0;
  if (state.view === "imagine-library") window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  window.requestAnimationFrame(() => {
    if (els.imagineGallery) els.imagineGallery.scrollTop = 0;
    if (state.view === "imagine-library") window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  });
}

function openImagineLibrary(options = {}) {
  if (state.accountScreenVisible) showAccountScreen(false);
  if (state.view === "detail") closeDetail({ fromHistory: true });
  const nextRemoteView = normalizeImagineRemoteView(options.remoteView || IMAGINE_REMOTE_VIEW_ALL);
  const nextPortfolioType = normalizeImaginePortfolioTypeFilter(options.portfolioType !== undefined ? options.portfolioType : state.imaginePortfolioTypeFilter);
  const nextDiscoverType = normalizeImagineDiscoverTypeFilter(options.discoverType !== undefined ? options.discoverType : state.imagineDiscoverTypeFilter);
  const nextAllFilesType = normalizeImagineAllFilesTypeFilter(options.allFilesType !== undefined ? options.allFilesType : state.imagineAllFilesTypeFilter);
  const forceRefresh = Boolean(options.refresh);
  if (forceRefresh && state.imagineRemoteBusy) {
    state.imagineRemoteToken += 1;
    state.imagineRemoteBusy = false;
  }
  setImagineRemoteView(nextRemoteView);
  if (nextRemoteView === IMAGINE_REMOTE_VIEW_ALL && options.portfolioType !== undefined) {
    setImaginePortfolioTypeFilter(nextPortfolioType);
  }
  if (nextRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER && options.discoverType !== undefined) {
    setImagineDiscoverTypeFilter(nextDiscoverType);
  }
  if (nextRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES && options.allFilesType !== undefined) {
    setImagineAllFilesTypeFilter(nextAllFilesType);
  }
  state.workspaceFolderId = "";
  state.filter = "all";
  if (els.searchInput) els.searchInput.value = "";
  state.view = "imagine-library";
  state.selectedItems.clear();
  const remoteKey = syncImagineRemoteAccountState();
  if (forceRefresh && remoteKey) {
    state.imagineRemoteCaches.delete(remoteKey);
    clearImagineRemoteState();
  }
  if (remoteKey && !activeImagineRemoteStateLoaded()) restoreImagineRemoteCache(remoteKey);
  state.imagineRemoteSuppressAutoLoadUntil = Date.now() + 900;
  syncWorkspaceView();
  renderImagineLibrary();
  resetImagineLibraryScroll();
  const hasRemoteCache = hasImagineRemoteCache(remoteKey);
  if (remoteKey && (forceRefresh || !hasRemoteCache) && !state.imagineRemoteBusy) {
    loadImagineRemoteLibrary({ reset: true }).catch((error) => showErrorPanel("Imagine failed", error.message));
  }
  if (!options.fromHistory) {
    history.pushState(
      {
        ...history.state,
        grokStudioView: "imagine-library",
        detailItemId: "",
        workspaceFolderId: "",
        imagineRemoteView: state.imagineRemoteView,
        imaginePortfolioTypeFilter: state.imaginePortfolioTypeFilter,
        imagineDiscoverTypeFilter: state.imagineDiscoverTypeFilter,
        imagineAllFilesTypeFilter: state.imagineAllFilesTypeFilter,
      },
      "",
      workspaceHistoryUrl({
        imagineLibrary: true,
        imagineRemoteView: state.imagineRemoteView,
        imaginePortfolioType: state.imaginePortfolioTypeFilter,
        imagineDiscoverType: state.imagineDiscoverTypeFilter,
        imagineAllFilesType: state.imagineAllFilesTypeFilter,
      }),
    );
  }
}

function syncGalleryRouteAfterFilter(previousView = state.view) {
  const currentUrl = new URL(window.location.href);
  const currentRouteIsGallery = history.state?.grokStudioView === "gallery"
    && !currentUrl.searchParams.has("detail")
    && currentUrl.searchParams.get("gallery") !== "1"
    && currentUrl.searchParams.get("imagine") !== "1";
  const nextState = {
    ...history.state,
    grokStudioView: "gallery",
    detailItemId: "",
    workspaceFolderId: state.workspaceFolderId,
    galleryFilter: state.filter,
  };
  const nextUrl = workspaceHistoryUrl();
  if (currentRouteIsGallery && previousView === "gallery") {
    history.replaceState(nextState, "", nextUrl);
    return;
  }
  const method = previousView === "folder-gallery" || previousView === "imagine-library"
    ? "pushState"
    : "replaceState";
  history[method](nextState, "", nextUrl);
}

function openSecondaryWorkspace(folderId, options = {}) {
  const folder = galleryFolderById(folderId);
  if (!folder?.parent_id) return;
  resetWorkspaceComposer();
  state.workspaceFolderId = folder.id;
  state.selectedPrimaryFolderId = folder.parent_id;
  state.galleryCollectionSelected = false;
  state.view = "gallery";
  syncWorkspaceView();
  renderGallery();
  if (!options.fromHistory) {
    history.pushState(
      { ...history.state, grokStudioView: "gallery", detailItemId: "", workspaceFolderId: folder.id },
      "",
      workspaceHistoryUrl(),
    );
  }
}

function folderCardIconHtml() {
  return `<span class="folder-card-icon" aria-hidden="true"><span></span></span>`;
}

function syncPrimaryFolderListRows() {
  const list = els.primaryFolderList;
  if (!list || !list.getClientRects().length) return;
  const panel = list.closest(".primary-folder-panel");
  const heading = panel?.querySelector(".folder-panel-heading");
  if (!panel || !heading) return;
  const panelStyle = getComputedStyle(panel);
  const panelGap = parseFloat(panelStyle.rowGap || panelStyle.gap || "0") || 0;
  const paddingY = (parseFloat(panelStyle.paddingTop) || 0) + (parseFloat(panelStyle.paddingBottom) || 0);
  const listStyle = getComputedStyle(list);
  const gap = parseFloat(listStyle.rowGap || listStyle.gap || "0") || 0;
  const availableHeight = panel.clientHeight - paddingY - heading.offsetHeight - panelGap;
  if (availableHeight <= 0) return;
  const rowHeight = Math.max(50, (availableHeight - (gap * 7)) / 8);
  const listHeight = (rowHeight * 8) + (gap * 7);
  list.style.setProperty("--primary-folder-row-height", `${rowHeight}px`);
  list.style.setProperty("--primary-folder-list-height", `${listHeight}px`);
}

function syncFolderGridRows(grid, visibleRows) {
  if (!grid || !grid.getClientRects().length) return;
  const rows = Math.max(1, Number(visibleRows) || 1);
  const style = getComputedStyle(grid);
  const gap = parseFloat(style.rowGap || style.gap || "0") || 0;
  const availableHeight = grid.clientHeight;
  if (availableHeight <= 0) return;
  const rowHeight = Math.max(50, (availableHeight - (gap * (rows - 1))) / rows);
  grid.style.setProperty("--secondary-folder-row-height", `${rowHeight}px`);
}

function syncSecondaryFolderGridRows() {
  syncFolderGridRows(els.secondaryFolderGrid, 8);
}

function schedulePrimaryFolderListRows() {
  requestAnimationFrame(() => requestAnimationFrame(syncPrimaryFolderListRows));
}

function scheduleSecondaryFolderGridRows() {
  requestAnimationFrame(() => requestAnimationFrame(syncSecondaryFolderGridRows));
}

function renderFolderGallery() {
  if (!els.primaryFolderList || !els.secondaryFolderGrid) return;
  const primaryFolders = primaryGalleryFolders();
  if (!primaryFolders.some((folder) => folder.id === state.selectedPrimaryFolderId)) {
    state.selectedPrimaryFolderId = "";
    state.galleryCollectionSelected = true;
  } else if (state.selectedPrimaryFolderId) {
    state.galleryCollectionSelected = false;
  }
  const selectedPrimary = galleryFolderById(state.selectedPrimaryFolderId);
  const secondaryFolders = selectedPrimary ? secondaryGalleryFolders(selectedPrimary.id) : [];
  if (!secondaryFolders.some((folder) => folder.id === state.selectedSecondaryFolderId)) {
    state.selectedSecondaryFolderId = "";
  }
  const collectionSelected = state.galleryCollectionSelected && !state.selectedPrimaryFolderId && !state.selectedSecondaryFolderId;
  els.collectionHeadingBtn?.classList.toggle("active", collectionSelected);
  els.collectionHeadingBtn?.setAttribute("aria-pressed", collectionSelected ? "true" : "false");
  if (els.secondaryFolderTitle) {
    els.secondaryFolderTitle.textContent = "";
  }
  document.querySelectorAll("[data-gallery-sort]").forEach((button) => {
    button.classList.toggle("active", button.dataset.gallerySort === state.gallerySort);
  });
  els.primaryFolderList.innerHTML = primaryFolders.length
    ? primaryFolders.map((folder) => `
      <button class="primary-folder-card${folder.id === state.selectedPrimaryFolderId ? " active" : ""}" type="button" draggable="true" data-primary-folder-id="${escapeHtml(folder.id)}">
        ${folderCardIconHtml()}
        <span class="folder-card-copy"><strong>${escapeHtml(folder.name)}</strong></span>
      </button>
    `).join("")
    : `<div class="folder-gallery-empty">No collection yet.</div>`;
  const maxSlot = Math.max(11, ...secondaryFolders.map((folder) => Number(folder.grid_slot) || 0)) + 4;
  const secondarySlots = Array.from({ length: maxSlot + 1 }, (_, slot) => {
    const folder = secondaryFolders.find((candidate) => Number(candidate.grid_slot) === slot);
    return folder
      ? `<button class="secondary-folder-card${folder.id === state.selectedSecondaryFolderId ? " active" : ""}" type="button" draggable="true" data-secondary-folder-id="${escapeHtml(folder.id)}" data-grid-slot="${slot}">
          ${folderCardIconHtml()}
          <strong>${escapeHtml(folder.name)}</strong>
        </button>`
      : `<button class="secondary-folder-slot" type="button" tabindex="-1" aria-label="Empty folder position" data-grid-slot="${slot}"></button>`;
  });
  els.secondaryFolderGrid.innerHTML = secondaryFolders.length
    ? secondarySlots.join("")
    : `<div class="folder-gallery-empty secondary-empty">${selectedPrimary ? "No workspace in this collection yet." : ""}</div>`;
  els.primaryFolderList.querySelectorAll("[data-primary-folder-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextId = button.dataset.primaryFolderId || "";
      state.selectedPrimaryFolderId = state.selectedPrimaryFolderId === nextId ? "" : nextId;
      state.selectedSecondaryFolderId = "";
      state.galleryCollectionSelected = !state.selectedPrimaryFolderId;
      renderFolderGallery();
    });
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("application/x-grok-primary-folder", button.dataset.primaryFolderId || "");
      button.classList.add("dragging");
    });
    button.addEventListener("dragend", () => button.classList.remove("dragging"));
    button.addEventListener("dragover", (event) => {
      if (!event.dataTransfer.types.includes("application/x-grok-primary-folder")) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    });
    button.addEventListener("drop", (event) => {
      event.preventDefault();
      reorderPrimaryFolder(
        event.dataTransfer.getData("application/x-grok-primary-folder"),
        button.dataset.primaryFolderId || "",
      ).catch((error) => toastError(error.message));
    });
  });
  els.secondaryFolderGrid.querySelectorAll("[data-secondary-folder-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextId = button.dataset.secondaryFolderId || "";
      state.selectedSecondaryFolderId = state.selectedSecondaryFolderId === nextId ? "" : nextId;
      state.galleryCollectionSelected = false;
      renderFolderGallery();
    });
    button.addEventListener("dblclick", () => openSecondaryWorkspace(button.dataset.secondaryFolderId || ""));
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("application/x-grok-secondary-folder", button.dataset.secondaryFolderId || "");
      button.classList.add("dragging");
    });
    button.addEventListener("dragend", () => button.classList.remove("dragging"));
  });
  els.secondaryFolderGrid.querySelectorAll("[data-grid-slot]").forEach((slot) => {
    slot.addEventListener("dragover", (event) => {
      if (!event.dataTransfer.types.includes("application/x-grok-secondary-folder")) return;
      event.preventDefault();
      slot.classList.add("drop-target");
      event.dataTransfer.dropEffect = "move";
    });
    slot.addEventListener("dragleave", () => slot.classList.remove("drop-target"));
    slot.addEventListener("drop", (event) => {
      event.preventDefault();
      slot.classList.remove("drop-target");
      moveSecondaryFolderToSlot(
        event.dataTransfer.getData("application/x-grok-secondary-folder"),
        slot.dataset.gridSlot,
      ).catch((error) => toastError(error.message));
    });
  });
  schedulePrimaryFolderListRows();
  scheduleSecondaryFolderGridRows();
}

function closeGalleryActionDialog() {
  state.galleryActionOverlay?.remove();
  state.galleryActionOverlay = null;
}

function openGalleryActionDialog({ title, message = "", value = null, confirmLabel = "Save" }) {
  closeGalleryActionDialog();
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "gallery-action-overlay";
    overlay.innerHTML = `
      <section class="gallery-action-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
        <h3>${escapeHtml(title)}</h3>
        ${message ? `<p>${escapeHtml(message)}</p>` : ""}
        ${value === null ? "" : `<input class="gallery-action-input" type="text" value="${escapeHtml(value)}" autocomplete="off" spellcheck="false" />`}
        <div class="gallery-action-buttons">
          <button class="gallery-action-cancel" type="button">Cancel</button>
          <button class="gallery-action-confirm gallery-action-${escapeHtml(confirmLabel.toLowerCase())}" type="button">${escapeHtml(confirmLabel)}</button>
        </div>
      </section>
    `;
    document.body.append(overlay);
    state.galleryActionOverlay = overlay;
    const input = overlay.querySelector(".gallery-action-input");
    const settle = (result) => {
      closeGalleryActionDialog();
      resolve(result);
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) settle(null);
    });
    overlay.querySelector(".gallery-action-cancel")?.addEventListener("click", () => settle(null));
    overlay.querySelector(".gallery-action-confirm")?.addEventListener("click", () => {
      settle(input ? input.value : true);
    });
    overlay.querySelector(".gallery-action-modal")?.addEventListener("keydown", (event) => {
      if (event.key === "Escape") settle(null);
      if (event.key === "Enter") {
        event.preventDefault();
        settle(input ? input.value : true);
      }
    });
    window.setTimeout(() => {
      input?.focus();
      input?.select();
    }, 0);
  });
}

async function makeGalleryFolder(options = {}) {
  const parentId = options.parentId === undefined
    ? (state.selectedPrimaryFolderId || "")
    : String(options.parentId || "");
  const level = parentId ? "workspace" : "collection";
  const name = await openGalleryActionDialog({
    title: `New ${level}`,
    value: "",
    confirmLabel: "Make",
  });
  if (name === null || !name.trim()) return;
  const data = await api("/api/gallery/folders", {
    method: "POST",
    body: JSON.stringify({ name: name.trim(), parent_id: parentId || undefined }),
  });
  state.galleryFolders = data.state?.gallery_folders || state.galleryFolders;
  if (!parentId && data.folder?.id) {
    state.selectedPrimaryFolderId = data.folder.id;
    state.galleryCollectionSelected = false;
  }
  if (options.render !== false) renderFolderGallery();
  return data.folder || null;
}

async function deleteGalleryFolder(folderId) {
  if (!folderId) return;
  const folder = galleryFolderById(folderId);
  if (!folder) return;
  const childIds = folder.parent_id
    ? [folder.id]
    : secondaryGalleryFolders(folder.id).map((child) => child.id);
  const itemCount = state.items.filter((item) => childIds.includes(itemGalleryFolderId(item))).length;
  const hasContents = itemCount > 0 || (!folder.parent_id && childIds.length > 0);
  const message = hasContents
    ? "The folder is not empty. Do you want to delete it?"
    : `Delete "${folder.name}"?`;
  const confirmed = await openGalleryActionDialog({
    title: "Delete folder",
    message,
    confirmLabel: "Delete",
  });
  if (!confirmed) return;
  await api("/api/gallery/folders/delete", {
    method: "POST",
    body: JSON.stringify({ folder_id: folder.id }),
  });
  return folder;
}

async function deleteSelectedGalleryFolder() {
  const folderId = state.selectedSecondaryFolderId || state.selectedPrimaryFolderId;
  const folder = await deleteGalleryFolder(folderId);
  if (!folder) return;
  state.selectedSecondaryFolderId = "";
  state.selectedPrimaryFolderId = folder.parent_id || "";
  await loadState();
  renderFolderGallery();
}

async function renameGalleryFolder(folderId) {
  if (!folderId) return;
  const folder = galleryFolderById(folderId);
  if (!folder) return;
  const name = await openGalleryActionDialog({
    title: "Rename folder",
    value: folder.name || "",
    confirmLabel: "Rename",
  });
  if (name === null || !name.trim() || name.trim() === folder.name) return;
  const data = await api("/api/gallery/folders/rename", {
    method: "POST",
    body: JSON.stringify({ folder_id: folder.id, name: name.trim() }),
  });
  state.galleryFolders = data.state?.gallery_folders || state.galleryFolders;
  return data.folder || null;
}

async function renameSelectedGalleryFolder() {
  const folderId = state.selectedSecondaryFolderId || state.selectedPrimaryFolderId;
  const folder = await renameGalleryFolder(folderId);
  if (!folder) return;
  renderFolderGallery();
}

function primaryHomeHistoryUrl() {
  const url = new URL(window.location.href);
  ["detail", "folder", "gallery", "imagine", "imagine_view", "imagine_all_files_type", "imagine_type"].forEach((key) => {
    url.searchParams.delete(key);
  });
  return `${url.pathname}${url.search}${url.hash}`;
}

function showAccountScreen(show, options = {}) {
  const nextVisible = Boolean(show);
  if (nextVisible && !state.accountScreenVisible && options.pushHistory) {
    history.pushState(
      {
        ...history.state,
        grokStudioAccount: true,
        grokStudioView: state.view,
        detailItemId: state.detailItemId || "",
        workspaceFolderId: state.workspaceFolderId || "",
      },
      "",
      primaryHomeHistoryUrl(),
    );
    state.accountHistoryOpen = true;
  } else if (!nextVisible && state.accountScreenVisible && !options.fromHistory && history.state?.grokStudioAccount) {
    history.replaceState(
      { ...history.state, grokStudioAccount: false },
      "",
      window.location.href,
    );
    state.accountHistoryOpen = false;
  }
  state.accountScreenVisible = nextVisible;
  document.querySelector(".workspace")?.classList.toggle("show-account", state.accountScreenVisible);
  if (els.accountOverlay) els.accountOverlay.hidden = !state.accountScreenVisible;
  if (state.accountScreenVisible) {
    loadAccounts().catch((error) => showErrorPanel("Accounts failed", error.message));
  } else {
    state.accountHistoryOpen = false;
  }
}

async function loadAccounts() {
  const data = await api("/api/accounts");
  state.accounts = data.accounts || [];
  state.imagineAccounts = data.imagine_accounts || [];
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || state.generationProvider || "build";
  renderAccounts();
  if (state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
}

function imagineStatusText(status) {
  if (status === "ok") return "OK";
  if (status === "expired") return "Expired";
  if (status === "unknown") return "Unknown";
  return "Checking";
}

function renderImagineStatus(account) {
  const status = state.imagineAccountStatuses?.[account.id]?.status || "checking";
  return `<span class="account-status-badge ${escapeHtml(status)}" aria-label="Imagine account status">${escapeHtml(imagineStatusText(status))}</span>`;
}

function renderBuildStatus(account) {
  const status = account?.exists === false ? "expired" : "ok";
  return `<span class="account-status-badge ${escapeHtml(status)}" aria-label="Build account status">${escapeHtml(imagineStatusText(status))}</span>`;
}

function normalizeAccountTier(tier) {
  const value = String(tier || "").toLowerCase();
  return ACCOUNT_TIERS.includes(value) ? value : "free";
}

function accountTierLabel(tier) {
  return ACCOUNT_TIER_LABELS[normalizeAccountTier(tier)] || "Free";
}

function renderAccountTierControl(account, provider) {
  const tier = normalizeAccountTier(account?.tier);
  const options = ACCOUNT_TIERS.map((value) => {
    const active = value === tier ? " active" : "";
    return `<button class="account-tier-option tier-${escapeHtml(value)}${active}" type="button" role="option" aria-selected="${value === tier ? "true" : "false"}" data-tier-value="${escapeHtml(value)}">${escapeHtml(accountTierLabel(value))}</button>`;
  }).join("");
  return `<div class="account-tier-control tier-${escapeHtml(tier)}" data-provider="${escapeHtml(provider)}" data-account-id="${escapeHtml(account.id)}" data-tier="${escapeHtml(tier)}">
    <button class="account-tier-button" type="button" aria-haspopup="listbox" aria-expanded="false">${escapeHtml(accountTierLabel(tier))}</button>
    <template class="account-tier-options">${options}</template>
  </div>`;
}

function closeAccountTierMenus() {
  els.accountList?.querySelectorAll(".account-tier-control.open").forEach((control) => {
    control.classList.remove("open");
    control.querySelector(".account-tier-button")?.setAttribute("aria-expanded", "false");
  });
  document.querySelector(".account-tier-floating-menu")?.remove();
}

function closeAccountTierMenusOnOutsideClick(event) {
  if (!(event.target instanceof Element)) return;
  if (event.target.closest(".account-tier-control")) return;
  if (event.target.closest(".account-tier-floating-menu")) return;
  closeAccountTierMenus();
}

function openAccountTierMenu(control, button) {
  closeAccountTierMenus();
  if (!control || !button) return;
  const template = control.querySelector(".account-tier-options");
  const menu = document.createElement("div");
  menu.className = "account-tier-floating-menu";
  menu.setAttribute("role", "listbox");
  menu.dataset.provider = control.dataset.provider || "";
  menu.dataset.accountId = control.dataset.accountId || "";
  menu.innerHTML = template?.innerHTML || "";
  document.body.appendChild(menu);
  const rect = button.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  const left = Math.min(Math.max(8, rect.left), window.innerWidth - menuRect.width - 8);
  const top = Math.max(8, rect.top - menuRect.height - 6);
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
  control.classList.add("open");
  button.setAttribute("aria-expanded", "true");
  menu.querySelectorAll(".account-tier-option").forEach((optionButton) => {
    optionButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      updateAccountTier(
        menu.dataset.provider || "",
        menu.dataset.accountId || "",
        optionButton.dataset.tierValue || "free",
      ).catch((error) => showErrorPanel("Accounts failed", error.message));
    });
  });
}

function renderAccounts() {
  if (!els.accountList) return;
  if (els.accountPathInput && !els.accountPathInput.value && (state.cliAuthFile || state.auth?.auth_file)) {
    els.accountPathInput.value = state.cliAuthFile || state.auth.auth_file;
  }
  renderImagineAccount();
  const selectedBuild = selectedBuildAccount();
  const accountColumnHtml = (provider, rows) => {
    const fixedRow = rows[0] || "";
    const sortableRows = rows.slice(1);
    return `<div class="account-column-body" data-account-column-provider="${escapeHtml(provider)}">
        ${fixedRow}
        <div class="account-column-scroll${fixedRow ? "" : " no-fixed"}" data-account-column-provider="${escapeHtml(provider)}">
          ${sortableRows.join("")}
        </div>
      </div>`;
  };
  const buildRows = state.accounts.map((account, index) => {
    const selected = state.generationProvider === "build" && selectedBuild?.id === account.id ? " active" : "";
    const fixed = index === 0 ? " account-row-fixed" : "";
    const draggable = index === 0 ? "false" : "true";
    const fixedAttr = index === 0 ? ' data-account-fixed="true"' : "";
    const label = account.email || account.label || "Grok account";
    return `<article class="account-row account-row-build${selected}${fixed}" role="button" tabindex="0" draggable="${draggable}" data-provider="build" data-account-id="${escapeHtml(account.id)}"${fixedAttr}>
      ${renderAccountTierControl(account, "build")}
      <div class="account-row-copy">
        <strong class="account-row-email">${escapeHtml(label)}</strong>
      </div>
      ${renderBuildStatus(account)}
      <button class="account-delete-button account-row-delete" type="button" data-delete-provider="build" data-account-id="${escapeHtml(account.id)}" aria-label="Delete Build account">x</button>
    </article>`;
  });
  const imagineRows = state.imagineAccounts.map((account, index) => {
    const selected = state.generationProvider === "imagine" && account.selected ? " active" : "";
    const fixed = index === 0 ? " account-row-fixed" : "";
    const draggable = index === 0 ? "false" : "true";
    const fixedAttr = index === 0 ? ' data-account-fixed="true"' : "";
    const label = account.email || account.label || "Imagine";
    return `<article class="account-row account-row-imagine${selected}${fixed}" role="button" tabindex="0" draggable="${draggable}" data-provider="imagine" data-account-id="${escapeHtml(account.id)}"${fixedAttr}>
      ${renderAccountTierControl(account, "imagine")}
      <div class="account-row-copy">
        <strong class="account-row-email">${escapeHtml(label)}</strong>
      </div>
      ${renderImagineStatus(account)}
      <button class="account-delete-button account-row-delete" type="button" data-delete-provider="imagine" data-account-id="${escapeHtml(account.id)}" aria-label="Delete Imagine account">x</button>
    </article>`;
  });
  els.accountList.innerHTML = `
    <section class="account-column" aria-label="Build accounts">
      ${accountColumnHtml("build", buildRows)}
    </section>
    <section class="account-column" aria-label="Imagine accounts">
      ${accountColumnHtml("imagine", imagineRows)}
    </section>`;
  els.accountList.querySelectorAll(".account-row-delete").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      if (button.dataset.deleteProvider === "imagine") {
        deleteImagineAccount(button.dataset.accountId).catch((error) => showErrorPanel("Imagine failed", error.message));
        return;
      }
      deleteBuildAccount(button.dataset.accountId).catch((error) => showErrorPanel("Accounts failed", error.message));
    });
  });
  els.accountList.querySelectorAll(".account-tier-button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const control = button.closest(".account-tier-control");
      const open = !control?.classList.contains("open");
      closeAccountTierMenus();
      if (!control || !open) return;
      openAccountTierMenu(control, button);
    });
  });
  els.accountList.querySelectorAll(".account-tier-control").forEach((control) => {
    ["pointerdown", "mousedown", "click"].forEach((eventName) => {
      control.addEventListener(eventName, (event) => event.stopPropagation());
    });
    control.addEventListener("dragstart", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
  });
  els.accountList.querySelectorAll(".account-row").forEach((row) => {
    const choose = () => {
      if (row.dataset.previewAccount === "true") return;
      if (row.classList.contains("active")) return;
      if (row.dataset.provider === "imagine") {
        selectImagineProvider(row.dataset.accountId).catch((error) => showErrorPanel("Imagine failed", error.message));
        return;
      }
      selectAccount(row.dataset.accountId).catch((error) => showErrorPanel("Accounts failed", error.message));
    };
    row.addEventListener("click", choose);
    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.code !== "Space") return;
      event.preventDefault();
      choose();
    });
    row.addEventListener("dragstart", (event) => {
      if (row.dataset.accountFixed === "true") {
        event.preventDefault();
        return;
      }
      state.accountDrag = {
        provider: row.dataset.provider || "",
        id: row.dataset.accountId || "",
      };
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("application/x-grok-account-provider", row.dataset.provider || "");
      event.dataTransfer.setData("application/x-grok-account-id", row.dataset.accountId || "");
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => {
      state.accountDrag = null;
      row.classList.remove("dragging");
    });
    row.addEventListener("dragover", (event) => {
      if (row.dataset.accountFixed === "true") return;
      if (state.accountDrag?.provider !== row.dataset.provider) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    });
    row.addEventListener("drop", (event) => {
      if (row.dataset.accountFixed === "true") return;
      event.preventDefault();
      event.stopPropagation();
      reorderAccountCard(
        row.dataset.provider || "",
        state.accountDrag?.id || event.dataTransfer.getData("application/x-grok-account-id"),
        row.dataset.accountId || "",
      ).catch((error) => showErrorPanel("Accounts failed", error.message));
      state.accountDrag = null;
    });
  });
  els.accountList.querySelectorAll(".account-column-body").forEach((column) => {
    column.addEventListener("dragover", (event) => {
      const provider = column.dataset.accountColumnProvider || "";
      if (state.accountDrag?.provider !== provider) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    });
    column.addEventListener("drop", (event) => {
      const provider = column.dataset.accountColumnProvider || "";
      if (state.accountDrag?.provider !== provider) return;
      if (event.target.closest(".account-row")) return;
      event.preventDefault();
      const list = provider === "imagine" ? state.imagineAccounts : state.accounts;
      const lastId = list[list.length - 1]?.id || "";
      reorderAccountCard(
        provider,
        state.accountDrag?.id || event.dataTransfer.getData("application/x-grok-account-id"),
        lastId,
      ).catch((error) => showErrorPanel("Accounts failed", error.message));
      state.accountDrag = null;
    });
  });
}

async function updateAccountTier(provider, accountId, tier) {
  if (!provider || !accountId) return;
  closeAccountTierMenus();
  const normalizedTier = normalizeAccountTier(tier);
  const targetList = provider === "imagine" ? state.imagineAccounts : state.accounts;
  const target = targetList.find((account) => account.id === accountId);
  if (target) target.tier = normalizedTier;
  renderAccounts();
  const data = await api("/api/accounts/tier", {
    method: "POST",
    body: JSON.stringify({ provider, id: accountId, tier: normalizedTier }),
  });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || state.generationProvider;
  renderAccounts();
}

async function refreshImagineAccountStatuses() {
  const ids = state.imagineAccounts.map((account) => account.id).filter(Boolean);
  const token = state.imagineAccountStatusToken + 1;
  state.imagineAccountStatusToken = token;
  state.imagineAccountStatuses = Object.fromEntries(ids.map((id) => [id, { status: "checking" }]));
  renderAccounts();
  if (!ids.length) return;
  const data = await api("/api/imagine/accounts/status", {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
  if (state.imagineAccountStatusToken !== token) return;
  const nextStatuses = {};
  (data.statuses || []).forEach((entry) => {
    if (!entry?.id) return;
    nextStatuses[entry.id] = { status: entry.status || "unknown" };
  });
  ids.forEach((id) => {
    if (!nextStatuses[id]) nextStatuses[id] = { status: "unknown" };
  });
  state.imagineAccountStatuses = nextStatuses;
  renderAccounts();
}

function renderImagineAccount() {
  const connected = Boolean(state.imagine?.connected);
  if (els.imagineCaptureBtn) els.imagineCaptureBtn.disabled = false;
  if (els.imagineLogoutBtn) els.imagineLogoutBtn.disabled = !connected;
  renderAuth(state.auth);
}

function selectedBuildAccount() {
  return state.accounts.find((account) => account.selected) || state.accounts[0] || null;
}

function selectedImagineAccount() {
  return state.imagineAccounts.find((account) => account.selected)
    || (state.generationProvider === "imagine" ? state.imagineAccounts[0] : null)
    || null;
}

function normalizeImagineRemoteView(view) {
  return [IMAGINE_REMOTE_VIEW_DISCOVER, IMAGINE_REMOTE_VIEW_ALL_FILES].includes(view)
    ? view
    : IMAGINE_REMOTE_VIEW_ALL;
}

function normalizeImagineMediaTypeFilter(type) {
  return [IMAGINE_MEDIA_TYPE_VIDEO, IMAGINE_MEDIA_TYPE_IMAGE].includes(type)
    ? type
    : IMAGINE_MEDIA_TYPE_ALL;
}

function normalizeImaginePortfolioTypeFilter(type) {
  return normalizeImagineMediaTypeFilter(type);
}

function normalizeImagineDiscoverTypeFilter(type) {
  return normalizeImagineMediaTypeFilter(type);
}

function normalizeImagineAllFilesTypeFilter(type) {
  return normalizeImagineMediaTypeFilter(type);
}

function setImaginePortfolioTypeFilter(type) {
  const nextType = normalizeImaginePortfolioTypeFilter(type);
  if (nextType === state.imaginePortfolioTypeFilter) return;
  state.imaginePortfolioTypeFillToken += 1;
  state.imaginePortfolioTypeFilter = nextType;
  state.imagineRemoteRenderSignature = "";
}

function setImagineDiscoverTypeFilter(type) {
  const nextType = normalizeImagineDiscoverTypeFilter(type);
  if (nextType === state.imagineDiscoverTypeFilter) return;
  state.imagineDiscoverTypeFillToken += 1;
  state.imagineDiscoverTypeFilter = nextType;
  state.imagineRemoteRenderSignature = "";
}

function setImagineAllFilesTypeFilter(type) {
  const nextType = normalizeImagineAllFilesTypeFilter(type);
  if (nextType === state.imagineAllFilesTypeFilter) return;
  state.imagineAllFilesTypeFillToken += 1;
  state.imagineAllFilesTypeFilter = nextType;
  state.imagineRemoteRenderSignature = "";
}

function setImagineRemoteView(view) {
  const nextView = normalizeImagineRemoteView(view);
  if (nextView === state.imagineRemoteView) return;
  cacheActiveImagineRemoteState();
  state.imagineAllFilesTypeFillToken += 1;
  state.imagineRemoteView = nextView;
  state.imagineRemoteAccountKey = "";
  state.imagineRemoteBusy = false;
  state.imagineRemoteRenderSignature = "";
}

function currentImagineMediaTypeFilter() {
  if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER) {
    return normalizeImagineDiscoverTypeFilter(state.imagineDiscoverTypeFilter);
  }
  if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES) {
    return normalizeImagineAllFilesTypeFilter(state.imagineAllFilesTypeFilter);
  }
  return normalizeImaginePortfolioTypeFilter(state.imaginePortfolioTypeFilter);
}

function syncImagineViewButtons() {
  const discover = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER;
  const allFiles = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES;
  els.imagineAllViewBtn?.classList.toggle("active", state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL);
  els.imagineAllViewBtn?.setAttribute("aria-pressed", String(state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL));
  els.imagineDiscoverViewBtn?.classList.toggle("active", discover);
  els.imagineDiscoverViewBtn?.setAttribute("aria-pressed", String(discover));
  els.imagineAllFilesViewBtn?.classList.toggle("active", allFiles);
  els.imagineAllFilesViewBtn?.setAttribute("aria-pressed", String(allFiles));
  const activeType = currentImagineMediaTypeFilter();
  document.querySelectorAll("[data-imagine-media-type]").forEach((button) => {
    const active = button.dataset.imagineMediaType === activeType;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function currentImagineRemoteAccountKey() {
  if (state.generationProvider !== "imagine") return "";
  const account = selectedImagineAccount();
  const id = String(account?.id || state.imagine?.id || state.imagine?.email || state.imagine?.label || "");
  const view = normalizeImagineRemoteView(state.imagineRemoteView);
  return id ? `imagine:${id}:${view}` : "";
}

function cacheActiveImagineRemoteState() {
  const key = state.imagineRemoteAccountKey;
  if (!key) return;
  if (!activeImagineRemoteStateLoaded() && imagineRemoteSnapshotLoaded(state.imagineRemoteCaches.get(key))) return;
  state.imagineRemoteCaches.set(key, {
    items: Array.isArray(state.imagineRemoteItems) ? state.imagineRemoteItems.slice() : [],
    cursor: state.imagineRemoteCursor || "",
    complete: Boolean(state.imagineRemoteComplete),
    loadedOnce: Boolean(state.imagineRemoteLoadedOnce),
    allFilesClassified: Boolean(state.imagineAllFilesClassified),
  });
}

function imagineRemoteSnapshotLoaded(snapshot) {
  if (!snapshot) return false;
  return Boolean(snapshot.loadedOnce || (Array.isArray(snapshot.items) && snapshot.items.length > 0));
}

function activeImagineRemoteStateLoaded() {
  return Boolean(state.imagineRemoteLoadedOnce || (state.imagineRemoteItems || []).length > 0);
}

function restoreImagineRemoteCache(key) {
  const cached = key ? state.imagineRemoteCaches.get(key) : null;
  if (!imagineRemoteSnapshotLoaded(cached)) return false;
  state.imagineRemoteItems = Array.isArray(cached.items) ? cached.items.slice() : [];
  state.imagineRemoteCursor = cached.cursor || "";
  state.imagineRemoteComplete = Boolean(cached.complete);
  state.imagineRemoteLoadedOnce = Boolean(cached.loadedOnce || state.imagineRemoteItems.length);
  state.imagineAllFilesClassified = Boolean(cached.allFilesClassified);
  state.imagineRemoteRenderSignature = "";
  return true;
}

function hasImagineRemoteCache(key) {
  if (!key) return false;
  if (key === state.imagineRemoteAccountKey && activeImagineRemoteStateLoaded()) return true;
  return imagineRemoteSnapshotLoaded(state.imagineRemoteCaches.get(key));
}

function clearImagineRemoteState() {
  state.imaginePortfolioTypeFillToken += 1;
  state.imagineDiscoverTypeFillToken += 1;
  state.imagineAllFilesTypeFillToken += 1;
  state.imagineAllFilesClassifyToken += 1;
  state.imagineAllFilesClassifyBusy = false;
  state.imagineAllFilesClassified = false;
  state.imagineRemoteItems = [];
  state.imagineRemoteCursor = "";
  state.imagineRemoteComplete = false;
  state.imagineRemoteLoadedOnce = false;
  state.imagineRemoteRenderSignature = "";
}

function syncImagineRemoteAccountState(options = {}) {
  const nextKey = currentImagineRemoteAccountKey();
  if (nextKey === state.imagineRemoteAccountKey && !options.forceReset) return nextKey;
  cacheActiveImagineRemoteState();
  state.imagineRemoteToken += 1;
  state.imagineRemoteBusy = false;
  state.imagineRemoteAccountKey = nextKey;
  const restored = !options.forceReset && restoreImagineRemoteCache(nextKey);
  if (!restored) {
    clearImagineRemoteState();
  }
  return nextKey;
}

function maybePrefetchImagineRemoteLibrary() {
  const key = syncImagineRemoteAccountState();
  if (!key || state.imagineRemoteBusy || hasImagineRemoteCache(key)) return;
  window.setTimeout(() => {
    if (currentImagineRemoteAccountKey() !== key || state.imagineRemoteAccountKey !== key) return;
    loadImagineRemoteLibrary({ reset: true, prefetch: true }).catch((error) => console.warn(error));
  }, 0);
}

async function registerAccount() {
  const label = els.accountNameInput?.value.trim() || "";
  const authFile = els.accountPathInput?.value.trim() || state.cliAuthFile || state.auth?.auth_file || "";
  if (!authFile) {
    toastError("Enter an auth file path.");
    return;
  }
  const data = await api("/api/accounts/register", {
    method: "POST",
    body: JSON.stringify({ label, auth_file: authFile }),
  });
  state.accounts = data.accounts || [];
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  renderAccounts();
  await loadState();
  toast("Account registered.");
}

async function selectAccount(accountId) {
  if (!accountId) return;
  const data = await api("/api/accounts/select", {
    method: "POST",
    body: JSON.stringify({ id: accountId }),
  });
  state.accounts = data.accounts || [];
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  renderAccounts();
  await loadState();
  toast("Account switched.");
}

async function startImagineLogin() {
  const data = await api("/api/imagine/login/start", {
    method: "POST",
    body: JSON.stringify({ anchor: browserWindowAnchor() }),
  });
  state.imagine = data.imagine || state.imagine;
  renderImagineAccount();
  toast("Imagine login opened.");
}

async function captureImagineLogin() {
  const data = await api("/api/imagine/login/capture", { method: "POST", body: "{}" });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || "imagine";
  syncImagineRemoteAccountState();
  renderAccounts();
  if (state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
  await loadState();
  maybePrefetchImagineRemoteLibrary();
  toast("Imagine connected.");
}

async function selectImagineProvider(accountId = "") {
  const data = await api("/api/imagine/select", {
    method: "POST",
    body: JSON.stringify({ id: accountId }),
  });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || "imagine";
  syncImagineRemoteAccountState();
  renderAccounts();
  if (state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
  await loadState();
  maybePrefetchImagineRemoteLibrary();
  toast("Imagine selected.");
}

async function clearImagineLogin() {
  const data = await api("/api/imagine/logout", { method: "POST", body: "{}" });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || null;
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  renderAccounts();
  if (state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
  await loadState();
  toast("Imagine logged out.");
}

async function deleteBuildAccount(accountId) {
  const account = state.accounts.find((entry) => entry.id === accountId) || selectedBuildAccount();
  if (!account?.id) {
    toastError("No Build account to delete.");
    return;
  }
  const label = account.email || account.label || "Build account";
  const confirmed = await openGalleryActionDialog({
    title: "Delete account",
    message: `Delete ${label}?`,
    confirmLabel: "Delete",
  });
  if (!confirmed) return;
  const data = await api("/api/accounts/delete", {
    method: "POST",
    body: JSON.stringify({ id: account.id }),
  });
  state.accounts = data.accounts || [];
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  renderAccounts();
  await loadState();
  toast("Build account deleted.");
}

async function deleteImagineAccount(accountId) {
  if (!accountId) {
    toastError("No Imagine account to delete.");
    return;
  }
  const account = state.imagineAccounts.find((entry) => entry.id === accountId);
  const label = account?.email || account?.label || "Imagine account";
  const confirmed = await openGalleryActionDialog({
    title: "Delete account",
    message: `Delete ${label}?`,
    confirmLabel: "Delete",
  });
  if (!confirmed) return;
  const data = await api("/api/imagine/delete", {
    method: "POST",
    body: JSON.stringify({ id: accountId }),
  });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || [];
  state.imagine = data.imagine || null;
  state.generationProvider = data.generation_provider || "build";
  syncImagineRemoteAccountState();
  renderAccounts();
  if (state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
  await loadState();
  toast("Imagine account deleted.");
}

async function reorderAccountCard(provider, draggedId, targetId) {
  if (!provider || !draggedId || !targetId || draggedId === targetId) return;
  const list = provider === "imagine" ? state.imagineAccounts.slice() : state.accounts.slice();
  const draggedIndex = list.findIndex((account) => account.id === draggedId);
  const targetIndex = list.findIndex((account) => account.id === targetId);
  if (draggedIndex < 0 || targetIndex < 0) return;
  if (draggedIndex === 0 || targetIndex === 0) return;
  const [dragged] = list.splice(draggedIndex, 1);
  list.splice(targetIndex, 0, dragged);
  const endpoint = provider === "imagine" ? "/api/imagine/reorder" : "/api/accounts/reorder";
  const data = await api(endpoint, {
    method: "POST",
    body: JSON.stringify({ provider, ids: list.map((account) => account.id) }),
  });
  state.accounts = data.accounts || state.accounts;
  state.imagineAccounts = data.imagine_accounts || state.imagineAccounts;
  state.imagine = data.imagine || state.imagine;
  state.generationProvider = data.generation_provider || state.generationProvider;
  renderAccounts();
  if (provider === "imagine" && state.accountScreenVisible) refreshImagineAccountStatuses().catch((error) => console.warn(error));
}

function browserWindowAnchor() {
  return {
    left: Number.isFinite(window.screenX) ? window.screenX : window.screenLeft,
    top: Number.isFinite(window.screenY) ? window.screenY : window.screenTop,
    width: Number(window.outerWidth || window.innerWidth || 0),
    height: Number(window.outerHeight || window.innerHeight || 0),
  };
}

function renderCategories() {
  els.categoryInput.value = defaultCategory();
}

function renderVideoChoices() {
  if (els.sourceVideoSelect) {
    els.sourceVideoSelect.value = state.selectedVideoId || "";
  }
}

function setImageModel(model) {
  const allowed = ["grok-imagine-image", "grok-imagine-image-quality"];
  state.imageModel = allowed.includes(model) ? model : "grok-imagine-image";
  localStorage.setItem("grokStudioImageModel", state.imageModel);
  if (els.imageModelInput && els.imageModelInput.value !== state.imageModel) {
    els.imageModelInput.value = state.imageModel;
  }
  syncCustomSelect(els.imageModelInput);
}

function setVideoModel(model) {
  const allowed = ["", VIDEO_MODEL_15, VIDEO_MODEL_15_PREVIEW];
  state.videoModel = allowed.includes(model) ? model : VIDEO_MODEL_15;
  localStorage.setItem("grokStudioVideoModel", state.videoModel);
  if (els.videoModelInput && els.videoModelInput.value !== state.videoModel) {
    els.videoModelInput.value = state.videoModel;
  }
  els.modelToggleButtons.forEach((button) => {
    button.classList.toggle("active", (button.dataset.videoModel || "") === state.videoModel);
  });
  syncCustomSelect(els.videoModelInput);
}

function renderJobs() {
  const active = state.jobs.filter((job) => !["done", "failed", "cancelled"].includes(job.status));
  if (els.jobSummary) els.jobSummary.textContent = active.length ? `${active.length} running` : "No active jobs";
  if (els.jobList) {
    els.jobList.innerHTML = state.jobs
      .filter((job) => !["done", "cancelled"].includes(job.status))
      .slice(0, 6)
      .map(jobChip)
      .join("");
  }
  renderDetailJobBadges();
  bindJobButtons();
}

function jobProgress(job) {
  const rawProgress = Number.isFinite(job.progress) ? job.progress : (job.status === "done" ? 100 : 0);
  return Math.max(0, Math.min(100, Math.round(rawProgress)));
}

function jobChipLabel(job) {
  const progress = jobProgress(job);
  if (job.status === "done") return "";
  if (job.status === "failed") {
    if (isCreditLimitError(job.error)) return "Credit Limit";
    return isModerationError(job.error) ? "Moderate" : "×";
  }
  if (job.status === "cancelled") return "";
  return `${progress}%`;
}

function jobChip(job) {
  const failed = job.status === "failed" ? " failed" : "";
  const creditLimit = job.status === "failed" && isCreditLimitError(job.error) ? " credit-limit" : "";
  const cancelled = job.status === "cancelled" ? " cancelled" : "";
  const done = job.status === "done" ? " done" : "";
  const running = !["done", "failed", "cancelled"].includes(job.status);
  const action = running ? "cancel" : "dismiss";
  const title = running ? "Cancel local job" : "Remove job from list";
  const error = job.error || "";
  const clickable = error && !isModerationError(error) && !isCreditLimitError(error) ? " error-clickable" : "";
  return `<span class="job-chip${failed}${creditLimit}${cancelled}${done}${clickable}" title="${escapeHtml(isCreditLimitError(error) ? "Credit Limit" : error || job.prompt || "")}" data-job-error="${escapeHtml(error)}">
    ${escapeHtml(jobChipLabel(job))}
    <button class="job-x" type="button" title="${title}" data-job-id="${escapeHtml(job.id)}" data-job-action="${action}">x</button>
  </span>`;
}

function jobContext(job) {
  return job?.context && typeof job.context === "object" ? job.context : {};
}

function detailGroupId(item) {
  return String(item?.metadata?.group_id || item?.id || "");
}

function mediaUrlKeys(value) {
  const url = sourceReferenceUrl(value);
  if (!url) return [];
  if (url.includes("/api/imagine/remote/media")) {
    try {
      const parsed = new URL(url, window.location.origin);
      const remoteUrl = parsed.searchParams.get("url");
      if (remoteUrl) return mediaUrlKeys(remoteUrl);
    } catch {
      // Continue with the proxy URL itself when it cannot be parsed.
    }
  }
  const bare = String(url).split("?")[0];
  const keys = new Set([bare]);
  try {
    keys.add(decodeURIComponent(bare));
  } catch {
    // Keep the encoded URL when the value is not safely decodable.
  }
  return [...keys].filter(Boolean);
}

function addMediaUrlKeys(target, value) {
  mediaUrlKeys(value).forEach((key) => target.add(key));
}

function addItemMediaUrlKeys(target, item) {
  if (!item) return;
  addMediaUrlKeys(target, item.local_url);
  addMediaUrlKeys(target, item.remote_url);
  (item.metadata?.source_images || []).forEach((value) => addMediaUrlKeys(target, value));
  addMediaUrlKeys(target, item.metadata?.start_image);
  (item.metadata?.reference_images || []).forEach((value) => addMediaUrlKeys(target, value));
}

function setsIntersect(left, right) {
  for (const value of left) {
    if (right.has(value)) return true;
  }
  return false;
}

function itemLocalUrlMatchesJobPreview(job, item) {
  const previewUrlKeys = new Set(mediaUrlKeys(jobContext(job).preview_url));
  if (!previewUrlKeys.size) return false;
  return setsIntersect(previewUrlKeys, new Set(mediaUrlKeys(item?.local_url)));
}

function preferredGalleryJobAnchor(job, candidates = []) {
  return candidates.find((item) => itemLocalUrlMatchesJobPreview(job, item))
    || candidates.find((item) => itemMatchesJobContext(job, item))
    || null;
}

function isVisualJob(job) {
  const kind = String(job?.kind || "");
  return kind === "image" || kind === "video" || kind.startsWith("image-") || kind.startsWith("video-");
}

function isRunningVisualJob(job) {
  return isVisualJob(job) && !["done", "failed", "cancelled"].includes(job.status);
}

function visualJobTargetType(job) {
  const kind = String(job?.kind || "");
  return kind === "video" || kind.startsWith("video-") ? "video" : "image";
}

function isDetailVisualJob(job, item = detailItem()) {
  if (!item || !job || !isVisualJob(job)) return false;
  if (["done", "cancelled"].includes(job.status)) return false;
  const context = jobContext(job);
  const groupId = detailGroupId(item);
  const contextGroupId = String(context.group_id || "");
  const parentId = String(context.parent_id || "");
  return Boolean(
    (groupId && contextGroupId && groupId === contextGroupId)
      || (parentId && (parentId === item.id || groupItemsFor(item).some((candidate) => candidate.id === parentId)))
  );
}

function detailVisualJobs(item = detailItem()) {
  return workspaceJobs().filter((job) => isDetailVisualJob(job, item));
}

function isDirectDetailVisualJob(job, item = detailItem()) {
  if (!item || !job || !isVisualJob(job)) return false;
  if (["done", "cancelled"].includes(job.status)) return false;
  const context = jobContext(job);
  const parentId = String(context.parent_id || "");
  if (parentId) return parentId === item.id;
  const contextGroupId = String(context.group_id || "");
  return Boolean(contextGroupId && contextGroupId === item.id);
}

function directDetailVisualJobs(item = detailItem()) {
  return workspaceJobs().filter((job) => isDirectDetailVisualJob(job, item));
}

function galleryVisualJobs() {
  if (state.filter === "prompt") return [];
  return workspaceJobs().filter((job) => {
    if (!isRunningVisualJob(job)) return false;
    const targetType = visualJobTargetType(job);
    if (state.filter === "image") return targetType === "image" || targetType === "video";
    if (state.filter === "video") return targetType === "video";
    return targetType === "image" || targetType === "video";
  });
}

function isStandaloneGalleryJob(job) {
  if (!isRunningVisualJob(job)) return false;
  const context = jobContext(job);
  return !String(context.parent_id || "") && !String(context.group_id || "");
}

function sortJobsNewestFirst(jobs) {
  return [...jobs].sort((a, b) => String(b.created_at || b.updated_at || b.id || "").localeCompare(String(a.created_at || a.updated_at || a.id || "")));
}

function promoteGalleryJobAnchorItems(items, jobs = galleryVisualJobs()) {
  let result = [...items];
  sortJobsNewestFirst(jobs).forEach((job) => {
    const candidates = Array.from(new Map([
      ...result,
      ...workspaceItems().filter((item) => item.type === "image" && item.local_url),
      ...uploadImageItems(),
    ].map((item) => [item.id, item])).values());
    const anchor = preferredGalleryJobAnchor(job, candidates);
    if (!anchor) return;
    result = [anchor, ...result.filter((item) => item.id !== anchor.id)];
  });
  return result;
}

function itemMatchesJobContext(job, item) {
  if (!job || !item) return false;
  const context = jobContext(job);
  const itemGroupId = detailGroupId(item);
  const contextGroupId = String(context.group_id || "");
  const parentId = String(context.parent_id || "");
  const previewUrlKeys = new Set(mediaUrlKeys(context.preview_url));
  const itemUrlKeys = new Set();
  addItemMediaUrlKeys(itemUrlKeys, item);
  const previewMatches = previewUrlKeys.size > 0 && setsIntersect(previewUrlKeys, itemUrlKeys);
  if (item.source === "upload-card") {
    return Boolean(
      (parentId && parentId === item.id)
        || (contextGroupId && contextGroupId === item.id)
        || previewMatches
    );
  }
  return Boolean(
    (parentId && parentId === item.id)
      || (contextGroupId && itemGroupId && contextGroupId === itemGroupId)
      || (parentId && groupItemsFor(item).some((candidate) => candidate.id === parentId))
      || previewMatches
  );
}

function visualJobMatchesItem(job, item) {
  if (!job || !item) return false;
  const targetType = visualJobTargetType(job);
  if (targetType === item.type) return itemMatchesJobContext(job, item);
  if (item.type === "image" && targetType === "video") {
    return itemMatchesJobContext(job, item);
  }
  return false;
}

function galleryProgressAnchorItems(items, jobs = galleryVisualJobs()) {
  if (!["all", "video"].includes(state.filter)) return items;
  let result = [...items];
  const sourceImages = [
    ...workspaceItems().filter((item) => item.type === "image" && item.local_url),
    ...uploadImageItems(),
  ].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));

  jobs
    .filter((job) => visualJobTargetType(job) === "video")
    .forEach((job) => {
      const sourceImage = preferredGalleryJobAnchor(job, sourceImages);
      if (!sourceImage) return;
      result = result.filter((item) => !visualJobMatchesItem(job, item) || item.id === sourceImage.id);
      if (!result.some((item) => item.id === sourceImage.id)) result.unshift(sourceImage);
    });

  return result;
}

function galleryJobForItem(item, jobs = galleryVisualJobs()) {
  return jobs.find((job) => visualJobMatchesItem(job, item)) || null;
}

function unmatchedGalleryJobs(items, jobs = galleryVisualJobs()) {
  return jobs.filter((job) => {
    const targetType = visualJobTargetType(job);
    if (state.filter === "image" && targetType !== "image") return false;
    if (state.filter === "video" && targetType !== "video") return false;
    return !items.some((item) => visualJobMatchesItem(job, item));
  });
}

function selectedDetailJob(item = detailItem()) {
  const selectedJobId = String(state.detailSelectedJobId || "");
  if (!selectedJobId || selectedJobId === "media") return null;
  return detailVisualJobs(item).find((job) => job.id === selectedJobId) || null;
}

function detailPrimaryVisualJob(item = detailItem()) {
  const jobs = directDetailVisualJobs(item);
  if (state.detailSelectedJobId === "media") return null;
  if (state.detailSelectedJobId) {
    const selected = selectedDetailJob(item);
    if (selected && selected.status === "failed" && isCreditLimitError(selected.error)) return null;
    if (selected) return selected;
  }
  const running = jobs.find((job) => job.status !== "failed");
  if (running) return running;
  return null;
}

function detailJobs(item = detailItem()) {
  return directDetailVisualJobs(item)
    .filter((job) => !["done", "cancelled"].includes(job.status))
    .slice(0, 3);
}

function detailJobBadgesHtml(item = detailItem()) {
  const jobs = detailJobs(item);
  if (!jobs.length) return "";
  return `<div class="detail-job-badges" aria-label="Jobs">
    ${jobs.map((job) => {
      const failed = job.status === "failed";
      const creditLimit = failed && isCreditLimitError(job.error);
      const action = failed ? "dismiss" : "";
      const label = creditLimit ? "Credit Limit" : (failed ? "×" : `${jobProgress(job)}%`);
      const title = failed
        ? (creditLimit ? "Credit Limit" : (isModerationError(job.error) ? "Moderate" : "Remove failed job"))
        : "Job progress";
      return `<button class="detail-job-badge${failed ? " failed" : ""}${creditLimit ? " credit-limit" : ""}" type="button" aria-label="${escapeHtml(title)}" data-job-id="${escapeHtml(job.id)}" data-job-action="${action}" ${action ? "" : "aria-disabled=\"true\""}><span class="detail-job-badge-label">${escapeHtml(label)}</span></button>`;
    }).join("")}
  </div>`;
}

function renderDetailJobBadges() {
  const wrap = els.detailScreen?.querySelector(".detail-media-wrap");
  if (!wrap) return;
  const host = wrap.querySelector(".detail-job-badges");
  const next = detailJobBadgesHtml();
  if (!next) {
    host?.remove();
    return;
  }
  if (host) host.outerHTML = next;
  else wrap.insertAdjacentHTML("beforeend", next);
}

function bindJobButtons() {
  $$(".job-chip.error-clickable").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest(".job-x")) return;
      if (isModerationError(chip.dataset.jobError)) return;
      showErrorPanel("Job failed", chip.dataset.jobError || "Unknown error");
    });
  });
  $$(".job-x, .detail-job-badge[data-job-action], .detail-generation-cancel[data-job-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.jobId;
      const action = button.dataset.jobAction;
      if (!id || !action) return;
      try {
        await api(`/api/jobs/${id}/${action}`, { method: "POST", body: "{}" });
        await loadState();
      } catch (error) {
        showErrorPanel("Job failed", error.message);
      }
    });
  });
}

function latestMediaItems(items) {
  const groups = new Map();
  items
    .filter((item) => ["image", "video"].includes(item.type) && item.local_url)
    .forEach((item) => {
      const groupId = item.metadata?.group_id || item.id;
      const group = groups.get(groupId) || [];
      group.push(item);
      groups.set(groupId, group);
    });
  return Array.from(groups.values())
    .map(representativeMediaItem)
    .filter(Boolean)
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function latestMediaItemsOfType(items, type) {
  const candidates = items.filter((item) => item.type === type && item.local_url);
  const visited = new Set();
  const representatives = [];
  candidates.forEach((item) => {
    if (visited.has(item.id)) return;
    const related = groupItemsFor(item, items);
    related.forEach((candidate) => visited.add(candidate.id));
    const representative = related
      .filter((candidate) => candidate.type === type && candidate.local_url)
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0];
    if (representative) representatives.push(representative);
  });
  return representatives
    .filter(Boolean)
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function currentGalleryMediaItems() {
  return Array.from(new Map([
    ...workspaceItems(),
    ...uploadImageItems(),
  ]
    .filter((item) => ["image", "video"].includes(item.type) && item.local_url)
    .map((item) => [item.id, item])).values());
}

function latestImageGalleryItems() {
  const scopeItems = currentGalleryMediaItems();
  return latestMediaItemsOfType(scopeItems, "image")
    .filter((item) => latestGroupItemOfType(item, "image", scopeItems)?.id === item.id)
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function latestLibraryGalleryItems() {
  const candidates = currentGalleryMediaItems();
  const visited = new Set();
  const representatives = [];
  candidates.forEach((item) => {
    if (visited.has(item.id)) return;
    const group = groupItemsFor(item, candidates);
    group.forEach((candidate) => visited.add(candidate.id));
    const representative = representativeMediaItem(group);
    if (representative) representatives.push(representative);
  });
  return Array.from(new Map(representatives.map((item) => [item.id, item])).values())
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function representativeMediaItem(group) {
  const items = Array.from(group || []).filter((item) => item?.local_url);
  const sorted = [...items].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  const preservedRepresentative = preservedImagineRepresentativeItem(sorted);
  if (preservedRepresentative) return preservedRepresentative;
  const latestVideo = sorted.find((item) => item.type === "video");
  if (latestVideo) return latestVideo;
  return sorted[0] || null;
}

function imagineRemoteItemId(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(
    metadata.remote_item_id
      || imagine.remote_item_id
      || (isImagineRemoteItem(item) ? item?.id : "")
      || "",
  );
}

function imaginePrimaryRemoteItemId(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(metadata.primary_remote_item_id || imagine.primary_remote_item_id || "");
}

function imaginePrimaryRemoteUrl(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(metadata.primary_remote_url || imagine.primary_remote_url || "");
}

function itemMatchesImaginePrimary(item, primaryId, primaryUrl) {
  const remoteId = imagineRemoteItemId(item);
  if (primaryId && remoteId && remoteId === primaryId) return true;
  const primaryKeys = new Set(mediaUrlKeys(primaryUrl));
  if (!primaryKeys.size) return false;
  const itemKeys = new Set();
  addItemMediaUrlKeys(itemKeys, item);
  return setsIntersect(primaryKeys, itemKeys);
}

function preservedImagineRepresentativeItem(items) {
  if (!Array.isArray(items) || !items.length) return null;
  const primaryId = items.map(imaginePrimaryRemoteItemId).find(Boolean) || "";
  const primaryUrl = items.map(imaginePrimaryRemoteUrl).find(Boolean) || "";
  if (!primaryId && !primaryUrl) return null;
  return items.find((item) => itemMatchesImaginePrimary(item, primaryId, primaryUrl)) || null;
}

function promptItems(items) {
  return items
    .filter((item) => item.type === "prompt")
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function uploadCardId(upload) {
  return upload?.id ? `upload-card:${upload.id}` : "";
}

function uploadImageItems(options = {}) {
  return (Array.isArray(state.uploads) ? state.uploads : [])
    .filter((upload) => {
      if (!upload?.local_url) return false;
      if (options.global || !state.workspaceFolderId) return true;
      return String(upload.gallery_folder_id || "") === state.workspaceFolderId;
    })
    .map((upload) => ({
      id: uploadCardId(upload),
      uploadId: upload.id || "",
      source: "upload-card",
      type: "image",
      mode: "upload",
      title: upload.name || upload.title || "Uploaded image",
      prompt: "",
      category: "Upload",
      tags: [],
      created_at: upload.created_at || upload.mtime || "",
      local_url: upload.local_url,
      file: upload.file || "",
      mime: upload.mime || "image",
      metadata: {
        upload_id: upload.id || "",
        gallery_folder_id: upload.gallery_folder_id || "",
      },
    }));
}

function galleryItemById(id) {
  return state.items.find((candidate) => candidate.id === id)
    || state.imagineRemoteItems.find((candidate) => candidate.id === id)
    || uploadImageItems({ global: true }).find((candidate) => candidate.id === id)
    || null;
}

function galleryTitleForFilter() {
  if (state.workspaceFolderId && ["all", "video", "image"].includes(state.filter)) return "Gallery";
  if (state.filter === "image") return "Image";
  if (state.filter === "video") return "Video";
  if (state.filter === "prompt") return "Prompt";
  return "Home";
}

function syncWorkspaceMediaTypeFilters(query = "") {
  const show = Boolean(state.workspaceFolderId)
    && state.view === "gallery"
    && !query
    && ["all", "video", "image"].includes(state.filter);
  if (els.workspaceMediaTypeFilters) {
    els.workspaceMediaTypeFilters.hidden = !show;
  }
  $$("[data-workspace-media-filter]").forEach((button) => {
    const active = show && button.dataset.workspaceMediaFilter === state.filter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function groupItemsFor(item, sourceItems = null) {
  if (!item) return [];
  const itemScope = Array.isArray(sourceItems)
    ? sourceItems
    : (isImagineRemoteItem(item) ? state.imagineRemoteItems : state.items);
  const candidates = itemScope.filter((candidate) => (
    ["image", "video"].includes(candidate.type) && candidate.local_url
  ));
  const ids = new Set([item.id]);
  const groupIds = new Set([detailGroupId(item)].filter(Boolean));
  const parentIds = new Set([String(item.metadata?.parent_id || "")].filter(Boolean));
  const urlKeys = new Set();
  addItemMediaUrlKeys(urlKeys, item);
  let changed = true;
  while (changed) {
    changed = false;
    for (const candidate of candidates) {
      const candidateId = String(candidate.id || "");
      const candidateGroupId = detailGroupId(candidate);
      const parentId = String(candidate.metadata?.parent_id || "");
      const candidateUrlKeys = new Set();
      addItemMediaUrlKeys(candidateUrlKeys, candidate);
      const related = ids.has(candidateId)
        || (candidateGroupId && groupIds.has(candidateGroupId))
        || (candidateGroupId && parentIds.has(candidateGroupId))
        || (parentId && ids.has(parentId))
        || (parentId && groupIds.has(parentId))
        || (parentId && parentIds.has(parentId))
        || setsIntersect(candidateUrlKeys, urlKeys);
      if (!related) continue;
      const previousIdCount = ids.size;
      const previousGroupCount = groupIds.size;
      const previousParentCount = parentIds.size;
      const previousUrlCount = urlKeys.size;
      if (candidateId) ids.add(candidateId);
      if (candidateGroupId) groupIds.add(candidateGroupId);
      if (parentId) {
        ids.add(parentId);
        parentIds.add(parentId);
      }
      addItemMediaUrlKeys(urlKeys, candidate);
      if (
        ids.size !== previousIdCount
        || groupIds.size !== previousGroupCount
        || parentIds.size !== previousParentCount
        || urlKeys.size !== previousUrlCount
      ) changed = true;
    }
  }
  const relatedItems = item.source === "upload-card" ? [item] : [];
  candidates
    .filter((candidate) => ids.has(candidate.id))
    .forEach((candidate) => relatedItems.push(candidate));
  const unique = new Map();
  relatedItems.forEach((candidate) => unique.set(candidate.id, candidate));
  return Array.from(unique.values())
    .sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
}

function latestGroupItemOfType(item, type, sourceItems = null) {
  return groupItemsFor(item, sourceItems)
    .filter((candidate) => candidate.type === type)
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0] || null;
}

function latestGroupItem(item, sourceItems = null) {
  return groupItemsFor(item, sourceItems)
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0] || null;
}

function latestDetailImage(item) {
  return latestGroupItemOfType(item, "image");
}

function selectedDetailImage(item) {
  const displayItem = detailDisplayItem(item);
  if (displayItem?.type === "image" && displayItem.local_url) return displayItem;
  return latestDetailImage(item);
}

function detailInitialItem(item) {
  return item || null;
}

function detailSourceThumbsFor(item) {
  if (item?.source === "upload-card") return [];
  const versions = groupItemsFor(item);
  const versionUrls = new Set(versions.map((candidate) => candidate.local_url).filter(Boolean));
  const urls = [];
  const addUrl = (value) => {
    const url = sourceReferenceUrl(value);
    if (!url || versionUrls.has(url) || urls.includes(url)) return;
    urls.push(url);
  };
  versions.forEach((candidate) => {
    (candidate.metadata?.source_images || []).forEach(addUrl);
    addUrl(candidate.metadata?.start_image);
    (candidate.metadata?.reference_images || []).forEach(addUrl);
  });
  return urls.map((url, index) => ({
    id: `source-${index}`,
    type: "source",
    local_url: url,
    title: "Original Image",
  }));
}

function mediaItemIdentity(item) {
  const identityUrls = mediaUrlKeys(item?.remote_url || item?.local_url);
  const url = identityUrls[0] || sourceReferenceUrl(item?.local_url);
  if (!url) return `id:${String(item?.id || "")}`;
  const bare = String(url).split("?")[0];
  try {
    return `url:${decodeURIComponent(bare)}`;
  } catch {
    return `url:${bare}`;
  }
}

function preferDetailThumb(existing, candidate) {
  const existingImported = existing?.mode === "import" || existing?.metadata?.imported === true;
  const candidateImported = candidate?.mode === "import" || candidate?.metadata?.imported === true;
  if (existingImported !== candidateImported) return existingImported ? candidate : existing;
  return String(candidate?.created_at || "").localeCompare(String(existing?.created_at || "")) > 0
    ? candidate
    : existing;
}

function imaginePostIdForItem(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(
    imagine.post_id
      || metadata.imagine_post_id
      || metadata.imagine_video_post_id
      || "",
  );
}

function imagineParentPostIdForItem(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(
    imagine.parent_post_id
      || metadata.parent_id
      || "",
  );
}

function imagineTreeVisitKey(item) {
  const postId = imaginePostIdForItem(item);
  if (postId) return `post:${postId}`;
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return String(
    metadata.imagine_asset_id
      || metadata.imagine_video_asset_id
      || imagine.asset_id
      || metadata.remote_item_id
      || imagine.remote_item_id
      || item?.request_id
      || item?.id
      || mediaItemIdentity(item)
      || "",
  );
}

function sortByCreatedAsc(items) {
  return [...items].sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
}

function imagineTreeOrderedItems(items) {
  const imported = items.filter(isImagineLineageItem);
  if (!imported.length) return items;
  const byPostId = new Map();
  const withoutPostId = [];
  imported.forEach((item) => {
    const postId = imaginePostIdForItem(item);
    if (postId && !byPostId.has(postId)) byPostId.set(postId, item);
    else withoutPostId.push(item);
  });
  const children = new Map();
  const roots = [];
  imported.forEach((item) => {
    const postId = imaginePostIdForItem(item);
    const parentId = imagineParentPostIdForItem(item);
    if (postId && parentId && byPostId.has(parentId) && parentId !== postId) {
      const list = children.get(parentId) || [];
      list.push(item);
      children.set(parentId, list);
    } else {
      roots.push(item);
    }
  });
  const ordered = [];
  const visited = new Set();
  const pushOrdered = (item) => {
    const key = imagineTreeVisitKey(item);
    if (key && visited.has(key)) return false;
    if (key) visited.add(key);
    ordered.push(item);
    return true;
  };
  const visitImageNode = (node) => {
    if (!pushOrdered(node)) return;
    const postId = imaginePostIdForItem(node);
    const childItems = sortByCreatedAsc(children.get(postId) || []);
    childItems
      .filter((child) => child.type === "video")
      .forEach((child) => {
        pushOrdered(child);
      });
    childItems
      .filter((child) => child.type === "image")
      .forEach(visitImageNode);
  };
  sortByCreatedAsc(roots)
    .filter((item) => item.type === "image")
    .forEach(visitImageNode);
  sortByCreatedAsc(roots)
    .filter((item) => item.type !== "image")
    .forEach((item) => {
      pushOrdered(item);
    });
  sortByCreatedAsc(imported).forEach((item) => {
    pushOrdered(item);
  });
  withoutPostId.forEach((item) => {
    pushOrdered(item);
  });
  return [
    ...ordered,
    ...items.filter((item) => !isImagineLineageItem(item)),
  ];
}

function detailScopeItemsFor(item) {
  if (isImagineRemoteItem(item)) return state.imagineRemoteItems;
  if (state.workspaceFolderId && state.detailNavView === "gallery") return currentGalleryMediaItems();
  return state.items;
}

function detailThumbVersionsFor(item) {
  const versions = [...detailSourceThumbsFor(item), ...groupItemsFor(item, detailScopeItemsFor(item))];
  const unique = new Map();
  versions.forEach((version) => {
    const identity = mediaItemIdentity(version);
    const existing = unique.get(identity);
    unique.set(identity, existing ? preferDetailThumb(existing, version) : version);
  });
  return imagineTreeOrderedItems(Array.from(unique.values()));
}

function selectedDetailSource() {
  if (!state.detailSelectedSourceUrl) return null;
  return detailSourceThumbsFor(detailItem())
    .find((source) => source.local_url === state.detailSelectedSourceUrl) || null;
}

function detailDisplayItem(item) {
  const source = selectedDetailSource();
  if (!source) return item;
  return {
    ...source,
    type: "image",
    title: source.title || "Original Image",
    prompt: item?.prompt || "",
    category: item?.category || "",
    tags: item?.tags || [],
    mime: "image",
    metadata: item?.metadata || {},
  };
}

function detailSourceAsImageSource(source) {
  if (!source?.local_url) return null;
  return {
    id: imageSourceId(),
    source: "detail-source",
    name: source.title || "Original Image",
    type: "image",
    size: 0,
    value: source.local_url,
    previewUrl: source.local_url,
    itemId: source.id || "",
  };
}

function hiddenMediaIconSvg() {
  return `<svg viewBox="0 0 96 96" aria-hidden="true">
    <path d="M12 49s13-22 36-22c6.5 0 12.3 1.7 17.2 4.2M77.5 39.2C83 44.3 86 49 86 49S73 71 48 71c-6.8 0-12.8-1.6-17.9-4.1" fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M40 56.5A12 12 0 0 1 56.4 40M29 17l42 62" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
  </svg>`;
}

function detailJobPreview(job, displayItem) {
  const context = jobContext(job);
  const url = context.preview_url || displayItem?.local_url || "";
  const type = context.preview_type || displayItem?.type || "image";
  return {
    url,
    type: type === "video" ? "video" : "image",
  };
}

function detailJobPreviewMediaHtml(job, displayItem, className) {
  const preview = detailJobPreview(job, displayItem);
  if (!preview.url) return `<div class="${className} detail-generation-fallback"></div>`;
  if (preview.type === "video") {
    return `<video class="${className}" src="${escapeHtml(preview.url)}" muted playsinline autoplay loop preload="metadata"></video>`;
  }
  return `<img class="${className}" src="${escapeHtml(preview.url)}" alt="" />`;
}

function detailJobThumbHtml(job, displayItem, active = true) {
  const failed = job.status === "failed";
  const creditLimit = failed && isCreditLimitError(job.error);
  const progress = failed ? jobProgress(job) : Math.max(1, jobProgress(job));
  const overlay = creditLimit
    ? `<span class="detail-job-thumb-limit">Credit<br>Limit</span>`
    : failed
    ? `<span class="detail-job-thumb-icon">${hiddenMediaIconSvg()}</span>`
    : `<span class="detail-job-thumb-progress" data-job-id="${escapeHtml(job.id)}">${progress}%</span>`;
  return `<button class="detail-thumb detail-job-thumb ${failed ? "failed" : "running"}${creditLimit ? " credit-limit" : ""}${active ? " active" : ""}" type="button" data-job-id="${escapeHtml(job.id)}" aria-label="${creditLimit ? "Credit limit" : failed ? "Failed generation" : "Creating media"}">
    ${detailJobPreviewMediaHtml(job, displayItem, "detail-job-thumb-media")}
    ${overlay}
  </button>`;
}

function detailGenerationMediaHtml(job, displayItem) {
  if (!job) return "";
  const failed = job.status === "failed";
  const progress = failed ? jobProgress(job) : Math.max(1, jobProgress(job));
  const content = failed
    ? `<div class="detail-generation-failed-icon">${hiddenMediaIconSvg()}</div>`
    : `<div class="detail-generation-status">
        <span class="detail-generation-progress" data-job-id="${escapeHtml(job.id)}">Creating ${progress}%</span>
        <span class="detail-generation-divider">|</span>
        <button class="detail-generation-cancel" type="button" data-job-id="${escapeHtml(job.id)}" data-job-action="cancel">Cancel</button>
      </div>`;
  return `<div class="detail-generation-frame ${failed ? "failed" : "running"}" data-job-id="${escapeHtml(job.id)}" aria-live="polite">
    ${detailJobPreviewMediaHtml(job, displayItem, "detail-generation-media")}
    ${failed ? "" : dotCssOverlayHtml("detail-generation-particles")}
    ${content}
  </div>`;
}

function sourceReferenceUrl(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object" && typeof value.url === "string") return value.url;
  return "";
}

function itemSearchMatches(item, query) {
  if (!query) return true;
  const haystack = [
    item.title,
    item.prompt,
    item.category,
    ...(item.tags || []),
  ].join(" ").toLowerCase();
  return haystack.includes(query);
}

function globalSearchItems(query) {
  const candidates = [
    ...latestMediaItemsOfType(state.items, "image"),
    ...latestMediaItemsOfType(state.items, "video"),
    ...uploadImageItems({ global: true }),
    ...promptItems(state.items),
  ];
  return Array.from(new Map(candidates.map((item) => [item.id, item])).values())
    .filter((item) => itemSearchMatches(item, query))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function renderGallery() {
  if (state.view === "folder-gallery") {
    renderFolderGallery();
    return;
  }
  if (state.view === "imagine-library") {
    renderImagineLibrary();
    return;
  }
  const query = els.searchInput.value.trim().toLowerCase();
  const scopedItems = workspaceItems();
  let items = [];
  if (query) {
    items = globalSearchItems(query);
  } else if (state.filter === "prompt") {
    items = promptItems(state.items);
  } else if (state.filter === "image") {
    items = latestImageGalleryItems();
  } else if (state.filter === "video") {
    items = latestMediaItemsOfType(scopedItems, "video");
  } else {
    items = latestLibraryGalleryItems();
  }
  const visualJobs = query ? [] : galleryVisualJobs();
  items = galleryProgressAnchorItems(items, visualJobs);
  items = promoteGalleryJobAnchorItems(items, visualJobs);

  const visibleIds = new Set(items.map((item) => item.id));
  for (const id of Array.from(state.selectedItems)) {
    if (!visibleIds.has(id)) state.selectedItems.delete(id);
  }
  updateSelectionControls();
  const title = query ? "Search" : galleryTitleForFilter();
  const titleButton = els.openFolderTitle;
  if (titleButton) titleButton.textContent = title;
  syncWorkspaceMediaTypeFilters(query);
  if (els.promptNewBtn) els.promptNewBtn.hidden = state.filter !== "prompt" || Boolean(query);
  const jobCards = query ? [] : sortJobsNewestFirst(unmatchedGalleryJobs(items, visualJobs));
  if (els.libraryCount) els.libraryCount.textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;
  els.gallery.classList.toggle("gallery-empty", !items.length && !jobCards.length);
  els.gallery.classList.toggle("prompt-gallery", state.filter === "prompt" && !query);
  els.gallery.classList.toggle("media-gallery", state.filter !== "prompt" || Boolean(query));
  els.gallery.classList.toggle("search-gallery", Boolean(query));
  els.gallery.dataset.filter = state.filter;
  if (!items.length && !jobCards.length) {
    els.gallery.innerHTML = `<div class="empty-state">No item yet.</div>`;
    return;
  }

  els.gallery.innerHTML = [
    ...jobCards.map(galleryJobCardHtml),
    ...items.map((item) => cardHtml(item, galleryJobForItem(item, visualJobs))),
  ].join("");
  bindCustomVideoPlayers();
  bindGalleryPreviewVideos();
  applyLocalGalleryOrderedReveal();
  $$(".media-card-open").forEach((button) => {
    button.addEventListener("click", (event) => {
      const item = galleryItemById(button.dataset.id);
      if (!item) return;
      if (state.filter === "image" && item.type === "image") {
        openDetail(item.id, { mode: "image" });
        return;
      }
      openDetail(item.id);
    });
  });
  $$(".prompt-card-open").forEach((button) => {
    button.addEventListener("click", () => {
      const item = state.items.find((candidate) => candidate.id === button.dataset.id);
      if (!item) return;
      openPromptEditor(item);
    });
  });
  $$(".extend-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      setSourceVideoFromLibrary(item, { scroll: true });
    });
  });
  $$(".to-video-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      setStartImageFromLibrary(item);
    });
  });
  $$(".copy-prompt-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const copied = await copyText(button.dataset.copy || "");
      if (!copied) toastError("Could not copy prompt.");
    });
  });
  $$(".download-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      downloadRelatedItems(item);
    });
  });
  $$(".delete-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      deleteSingleGalleryItem(item).catch((error) => toastError(error.message));
    });
  });
  $$(".move-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedItems.clear();
      state.selectedItems.add(button.dataset.id);
      openMoveToGalleryDialog();
    });
  });
  bindCardSelectionControls();
  $$(".card[draggable='true']").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", card.dataset.itemId);
      event.dataTransfer.setData("application/x-grok-item-id", card.dataset.itemId);
      event.dataTransfer.setData("application/x-grok-item-type", card.dataset.itemType);
      event.dataTransfer.effectAllowed = "copy";
    });
  });
}

function isImagineImportedItem(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return Boolean(
    metadata.import_source === "imagine"
      || metadata.source === "imagine-import"
      || metadata.source === "imagine-remote-import"
      || metadata.imagine_imported
      || imagine.imported
      || imagine.import_source === "imagine"
      || item?.import_source === "imagine"
      || item?.source === "imagine-import"
      || item?.mode === "imagine-import",
  );
}

function isImagineRemoteItem(item) {
  if (!item || isImagineImportedItem(item)) return false;
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return Boolean(
    item?.mode === "imagine-remote"
      || item?.source === "imagine-remote"
      || metadata.source === "imagine-remote"
      || imagine.remote,
  );
}

function isImagineLineageItem(item) {
  return isImagineImportedItem(item) || isImagineRemoteItem(item);
}

function bindGalleryCardEvents(root = document, options = {}) {
  const queryAll = (selector) => Array.from((root || document).querySelectorAll(selector));
  bindCustomVideoPlayers();
  bindGalleryPreviewVideos(root);
  queryAll(".media-card-open").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      if (!item) return;
      if (options.imageModeDetail && item.type === "image") {
        openDetail(item.id, { mode: "image" });
        return;
      }
      openDetail(item.id);
    });
  });
  queryAll(".prompt-card-open").forEach((button) => {
    button.addEventListener("click", () => {
      const item = state.items.find((candidate) => candidate.id === button.dataset.id);
      if (!item) return;
      openPromptEditor(item);
    });
  });
  queryAll(".extend-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      setSourceVideoFromLibrary(item, { scroll: true });
    });
  });
  queryAll(".to-video-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      setStartImageFromLibrary(item);
    });
  });
  queryAll(".copy-prompt-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const copied = await copyText(button.dataset.copy || "");
      if (!copied) toastError("Could not copy prompt.");
    });
  });
  queryAll(".download-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      downloadRelatedItems(item);
    });
  });
  queryAll(".delete-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const item = galleryItemById(button.dataset.id);
      deleteSingleGalleryItem(item).catch((error) => toastError(error.message));
    });
  });
  queryAll(".move-card-btn").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedItems.clear();
      state.selectedItems.add(button.dataset.id);
      openMoveToGalleryDialog();
    });
  });
  bindCardSelectionControls(root);
  queryAll(".card[draggable='true']").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", card.dataset.itemId);
      event.dataTransfer.setData("application/x-grok-item-id", card.dataset.itemId);
      event.dataTransfer.setData("application/x-grok-item-type", card.dataset.itemType);
      event.dataTransfer.effectAllowed = "copy";
    });
  });
}

function imagineRemoteMediaCandidates() {
  return (state.imagineRemoteItems || [])
    .filter((item) => ["image", "video"].includes(item.type) && item.local_url && isImagineRemoteItem(item));
}

function imagineAllFilesTypeItems(type = state.imagineAllFilesTypeFilter) {
  const typeFilter = normalizeImagineAllFilesTypeFilter(type);
  const candidates = imagineRemoteMediaCandidates();
  const filtered = typeFilter === IMAGINE_ALL_FILES_TYPE_ALL
    ? candidates
    : candidates.filter((item) => item.type === typeFilter);
  return Array.from(new Map(filtered.map((item) => [item.id, item])).values());
}

function imaginePortfolioTypeItems(type = state.imaginePortfolioTypeFilter) {
  const typeFilter = normalizeImaginePortfolioTypeFilter(type);
  if (typeFilter === IMAGINE_PORTFOLIO_TYPE_ALL) return null;
  const candidates = imagineRemoteMediaCandidates()
    .filter((item) => item.type === typeFilter);
  const visited = new Set();
  const representatives = [];
  candidates.forEach((item) => {
    if (visited.has(item.id)) return;
    const group = groupItemsFor(item).filter(isImagineRemoteItem);
    group.forEach((candidate) => visited.add(candidate.id));
    const representative = group
      .filter((candidate) => candidate.type === typeFilter && candidate.local_url)
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0];
    if (representative) representatives.push(representative);
  });
  return Array.from(new Map(representatives.map((item) => [item.id, item])).values());
}

function imagineDiscoverTypeItems(type = state.imagineDiscoverTypeFilter) {
  const typeFilter = normalizeImagineDiscoverTypeFilter(type);
  if (typeFilter === IMAGINE_DISCOVER_TYPE_ALL) return null;
  return Array.from(new Map(
    imagineRemoteMediaCandidates()
      .filter((item) => item.type === typeFilter)
      .map((item) => [item.id, item]),
  ).values());
}

function imagineRemoteRepresentativeItems() {
  const candidates = imagineRemoteMediaCandidates();
  if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES) {
    return imagineAllFilesTypeItems();
  }
  if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL) {
    const typedItems = imaginePortfolioTypeItems();
    if (typedItems) return typedItems;
  }
  if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER) {
    const typedItems = imagineDiscoverTypeItems();
    if (typedItems) return typedItems;
  }
  const preserveAppendOrder = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER;
  if (!preserveAppendOrder) {
    candidates.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  }
  const visited = new Set();
  const representatives = [];
  candidates.forEach((item) => {
    if (visited.has(item.id)) return;
    const group = groupItemsFor(item).filter(isImagineRemoteItem);
    group.forEach((candidate) => visited.add(candidate.id));
    const representative = representativeMediaItem(group);
    if (representative) representatives.push(representative);
  });
  const uniqueRepresentatives = Array.from(new Map(representatives.map((item) => [item.id, item])).values());
  return preserveAppendOrder
    ? uniqueRepresentatives
    : uniqueRepresentatives.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

async function fillImagineAllFilesTypeIfNeeded(type = state.imagineAllFilesTypeFilter) {
  const typeFilter = normalizeImagineAllFilesTypeFilter(type);
  if (typeFilter === IMAGINE_ALL_FILES_TYPE_ALL) return;
  const token = state.imagineAllFilesTypeFillToken + 1;
  state.imagineAllFilesTypeFillToken = token;
  for (let page = 0; page < IMAGINE_ALL_FILES_TYPE_FILL_MAX_PAGES; page += 1) {
    if (token !== state.imagineAllFilesTypeFillToken) return;
    if (state.view !== "imagine-library" || state.imagineRemoteView !== IMAGINE_REMOTE_VIEW_ALL_FILES) return;
    if (normalizeImagineAllFilesTypeFilter(state.imagineAllFilesTypeFilter) !== typeFilter) return;
    if (imagineAllFilesTypeItems(typeFilter).length >= IMAGINE_REMOTE_PAGE_SIZE) return;
    if (state.imagineRemoteBusy || state.imagineRemoteComplete || !state.imagineRemoteCursor) return;
    await loadImagineRemoteLibrary({ automatic: true, typeFill: true });
  }
}

async function fillImaginePortfolioTypeIfNeeded(type = state.imaginePortfolioTypeFilter) {
  const typeFilter = normalizeImaginePortfolioTypeFilter(type);
  if (typeFilter === IMAGINE_PORTFOLIO_TYPE_ALL) return;
  const token = state.imaginePortfolioTypeFillToken + 1;
  state.imaginePortfolioTypeFillToken = token;
  for (let page = 0; page < IMAGINE_ALL_FILES_TYPE_FILL_MAX_PAGES; page += 1) {
    if (token !== state.imaginePortfolioTypeFillToken) return;
    if (state.view !== "imagine-library" || state.imagineRemoteView !== IMAGINE_REMOTE_VIEW_ALL) return;
    if (normalizeImaginePortfolioTypeFilter(state.imaginePortfolioTypeFilter) !== typeFilter) return;
    if ((imaginePortfolioTypeItems(typeFilter) || []).length >= IMAGINE_REMOTE_PAGE_SIZE) return;
    if (state.imagineRemoteBusy || state.imagineRemoteComplete || !state.imagineRemoteCursor) return;
    await loadImagineRemoteLibrary({ automatic: true, typeFill: true });
  }
}

async function fillImagineDiscoverTypeIfNeeded(type = state.imagineDiscoverTypeFilter) {
  const typeFilter = normalizeImagineDiscoverTypeFilter(type);
  if (typeFilter === IMAGINE_DISCOVER_TYPE_ALL) return;
  const token = state.imagineDiscoverTypeFillToken + 1;
  state.imagineDiscoverTypeFillToken = token;
  for (let page = 0; page < IMAGINE_ALL_FILES_TYPE_FILL_MAX_PAGES; page += 1) {
    if (token !== state.imagineDiscoverTypeFillToken) return;
    if (state.view !== "imagine-library" || state.imagineRemoteView !== IMAGINE_REMOTE_VIEW_DISCOVER) return;
    if (normalizeImagineDiscoverTypeFilter(state.imagineDiscoverTypeFilter) !== typeFilter) return;
    if ((imagineDiscoverTypeItems(typeFilter) || []).length >= IMAGINE_REMOTE_PAGE_SIZE) return;
    if (state.imagineRemoteBusy || state.imagineRemoteComplete || !state.imagineRemoteCursor) return;
    await loadImagineRemoteLibrary({ automatic: true, typeFill: true });
  }
}

function mergeImagineRemoteItems(items = []) {
  if (
    state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES
    || state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER
    || state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL
  ) {
    const merged = Array.isArray(state.imagineRemoteItems) ? state.imagineRemoteItems.slice() : [];
    const indexes = new Map(merged.map((item, index) => [item.id, index]));
    items.forEach((item) => {
      if (!item?.id) return;
      if (indexes.has(item.id)) {
        merged[indexes.get(item.id)] = item;
        return;
      }
      indexes.set(item.id, merged.length);
      merged.push(item);
    });
    state.imagineRemoteItems = merged;
    return;
  }
  const merged = new Map((state.imagineRemoteItems || []).map((item) => [item.id, item]));
  items.forEach((item) => {
    if (!item?.id) return;
    merged.set(item.id, item);
  });
  state.imagineRemoteItems = Array.from(merged.values())
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

function imagineGalleryMediaReady(media) {
  if (!media) return true;
  const tagName = String(media.tagName || "").toLowerCase();
  if (tagName === "img") {
    return Boolean(media.complete && media.naturalWidth > 0) || Boolean(media.dataset.loadFailed);
  }
  if (tagName === "video") {
    return Number(media.readyState || 0) >= 2 || Boolean(media.error) || Boolean(media.dataset.loadFailed);
  }
  return true;
}

function waitForImagineCurrentMediaReady() {
  if (!els.imagineGallery || state.view !== "imagine-library") return Promise.resolve();
  const mediaItems = Array.from(
    els.imagineGallery.querySelectorAll(".card[data-item-id] .preview > img, .card[data-item-id] .preview > video"),
  ).filter((media) => !imagineGalleryMediaReady(media));
  if (!mediaItems.length) return Promise.resolve();

  return new Promise((resolve) => {
    const pending = new Set(mediaItems);
    const cleanups = [];
    let finished = false;

    const finish = () => {
      if (finished) return;
      finished = true;
      cleanups.forEach((cleanup) => cleanup());
      resolve();
    };
    const markReady = (media) => {
      pending.delete(media);
      if (!pending.size) finish();
    };
    mediaItems.forEach((media) => {
      const tagName = String(media.tagName || "").toLowerCase();
      const events = tagName === "video"
        ? ["loadeddata", "canplay", "canplaythrough", "error"]
        : ["load", "error"];
      const handler = (event) => {
        if (event.type === "error") media.dataset.loadFailed = "1";
        markReady(media);
      };
      events.forEach((eventName) => media.addEventListener(eventName, handler, { once: true }));
      cleanups.push(() => events.forEach((eventName) => media.removeEventListener(eventName, handler)));
      if (tagName === "img") {
        media.loading = "eager";
      } else if (tagName === "video") {
        media.preload = "auto";
        if (media.networkState === 0) {
          try {
            media.load();
          } catch {
            // Metadata loading can be browser-managed; a failed nudge should not stop waiting.
          }
        }
      }
    });
    window.requestAnimationFrame(() => {
      mediaItems.forEach((media) => {
        if (imagineGalleryMediaReady(media)) markReady(media);
      });
    });
  });
}

function preloadImagineRemoteItemMedia(item) {
  if (!item || !["image", "video"].includes(item.type) || !item.local_url) return Promise.resolve();
  const url = String(item.local_url || "");
  if (!url) return Promise.resolve();

  return new Promise((resolve) => {
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      resolve();
    };

    if (item.type === "image") {
      const image = new Image();
      image.decoding = "async";
      image.onload = finish;
      image.onerror = finish;
      image.src = url;
      if (image.complete) finish();
      return;
    }

    const video = document.createElement("video");
    const events = ["loadeddata", "canplay", "canplaythrough", "error"];
    const cleanup = () => {
      events.forEach((eventName) => video.removeEventListener(eventName, handler));
      video.removeAttribute("src");
      try {
        video.load();
      } catch {
        // The preload element is temporary; cleanup failure is harmless.
      }
    };
    const handler = () => {
      cleanup();
      finish();
    };
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    events.forEach((eventName) => video.addEventListener(eventName, handler, { once: true }));
    video.src = url;
    try {
      video.load();
    } catch {
      cleanup();
      finish();
    }
    if (Number(video.readyState || 0) >= 2 || video.error) {
      cleanup();
      finish();
    }
  });
}

function preloadImagineRemoteItems(items = []) {
  const seen = new Set();
  const tasks = [];
  (Array.isArray(items) ? items : []).forEach((item) => {
    if (!item || !["image", "video"].includes(item.type) || !item.local_url) return;
    const key = `${item.type}:${item.local_url}`;
    if (seen.has(key)) return;
    seen.add(key);
    tasks.push(preloadImagineRemoteItemMedia(item));
  });
  return Promise.all(tasks).then(() => undefined);
}

async function loadImagineRemoteLibrary(options = {}) {
  const key = syncImagineRemoteAccountState();
  if (!key || state.imagineRemoteBusy) return;
  const reset = Boolean(options.reset);
  const automatic = Boolean(options.automatic);
  const prefetch = Boolean(options.prefetch);
  const typeFill = Boolean(options.typeFill);
  if (reset) {
    clearImagineRemoteState();
    state.imagineRemoteCaches.delete(key);
  } else if (state.imagineRemoteComplete || (!state.imagineRemoteLoadedOnce && automatic)) {
    return;
  }
  const waitBeforeAppend = automatic
    && !reset
    && !prefetch
    && !typeFill
    && state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL
    && state.imagineRemoteLoadedOnce
    && state.imagineRemoteItems.length > 0;
  const token = state.imagineRemoteToken + 1;
  state.imagineRemoteToken = token;
  state.imagineRemoteBusy = true;
  if (state.view === "imagine-library") renderImagineLibrary();
  try {
    const data = await api("/api/imagine/remote/list", {
      method: "POST",
      body: JSON.stringify({
        view: state.imagineRemoteView,
        limit: IMAGINE_REMOTE_PAGE_SIZE,
        ...(state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES
          ? {
              scan_limit: 80,
              workspace_limit: 160,
              include_conversations: false,
              raw_files: true,
            }
          : {}),
        cursor: state.imagineRemoteCursor || "",
      }),
    });
    if (
      state.imagineRemoteToken !== token
      || state.imagineRemoteAccountKey !== key
      || currentImagineRemoteAccountKey() !== key
    ) return;
    const incomingItems = Array.isArray(data.items) ? data.items : [];
    if (waitBeforeAppend) {
      await Promise.all([
        waitForImagineCurrentMediaReady(),
        preloadImagineRemoteItems(incomingItems),
      ]);
      if (
        state.imagineRemoteToken !== token
        || state.imagineRemoteAccountKey !== key
        || currentImagineRemoteAccountKey() !== key
      ) return;
    }
    mergeImagineRemoteItems(incomingItems);
    state.imagineRemoteCursor = String(data.next_cursor || "");
    state.imagineRemoteComplete = !state.imagineRemoteCursor;
    state.imagineRemoteLoadedOnce = true;
    cacheActiveImagineRemoteState();
  } catch (error) {
    if (
      state.imagineRemoteToken !== token
      || state.imagineRemoteAccountKey !== key
      || currentImagineRemoteAccountKey() !== key
    ) return;
    if (/timed?\s*out|read operation timed out/i.test(String(error?.message || "")) && (automatic || state.imagineRemoteItems.length)) {
      console.warn("Imagine remote page timed out; keeping existing items.", error);
      return;
    }
    if (prefetch) {
      console.warn("Imagine prefetch failed.", error);
      return;
    }
    showErrorPanel("Imagine failed", error.message);
  } finally {
    if (
      state.imagineRemoteToken === token
      && state.imagineRemoteAccountKey === key
      && currentImagineRemoteAccountKey() === key
    ) {
      state.imagineRemoteBusy = false;
      cacheActiveImagineRemoteState();
      if (state.view === "imagine-library") {
        renderImagineLibrary();
        if (!typeFill) {
          if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL) {
            fillImaginePortfolioTypeIfNeeded().catch((error) => console.warn(error));
          } else if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER) {
            fillImagineDiscoverTypeIfNeeded().catch((error) => console.warn(error));
          }
        }
      }
    }
  }
}

function renderImagineLibrary() {
  if (!els.imagineGallery) return;
  const items = imagineRemoteRepresentativeItems();
  const discoverView = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER;
  const allFilesView = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES;
  const remoteBusy = state.imagineRemoteBusy || (allFilesView && state.imagineAllFilesClassifyBusy && !state.imagineAllFilesClassified);
  const allFilesTypeFilter = normalizeImagineAllFilesTypeFilter(state.imagineAllFilesTypeFilter);
  const hidePartialTypeFill = allFilesView
    && allFilesTypeFilter !== IMAGINE_ALL_FILES_TYPE_ALL
    && remoteBusy
    && items.length > 0
    && items.length < IMAGINE_REMOTE_PAGE_SIZE;
  const renderItems = hidePartialTypeFill ? [] : items;
  const loadingLabel = "Loading . . .";
  const emptyLabel = allFilesView ? "No Imagine file yet." : (discoverView ? "No Discover item yet." : "No Imagine item yet.");
  syncImagineViewButtons();
  if (els.imagineImportBtn) {
    els.imagineImportBtn.disabled = false;
    els.imagineImportBtn.textContent = "Selected Import";
  }
  const visibleIds = new Set(renderItems.map((item) => item.id));
  for (const id of Array.from(state.selectedItems)) {
    if (!visibleIds.has(id)) state.selectedItems.delete(id);
  }
  updateSelectionControls();
  els.imagineGallery.classList.toggle("gallery-empty", !renderItems.length && !remoteBusy);
  els.imagineGallery.dataset.filter = allFilesView ? "imagine-all-files" : (discoverView ? "imagine-discover" : "imagine");
  const setLoadingIndicator = () => {
    let indicator = els.imagineGallery.querySelector(".imagine-remote-loading");
    if (remoteBusy) {
      if (!indicator) {
        indicator = document.createElement("div");
        indicator.className = "empty-state imagine-remote-loading";
        indicator.textContent = loadingLabel;
        els.imagineGallery.appendChild(indicator);
      }
    } else if (indicator) {
      indicator.remove();
    }
  };
  const updateExistingCardSelection = () => {
    els.imagineGallery.querySelectorAll(".card[data-item-id]").forEach((card) => {
      const selected = state.selectedItems.has(card.dataset.itemId || "");
      card.classList.toggle("selected", selected);
      card.querySelector(".item-select")?.setAttribute("aria-pressed", String(selected));
    });
  };
  const renderSignature = JSON.stringify({
    view: state.imagineRemoteView,
    portfolioType: state.imaginePortfolioTypeFilter,
    discoverType: state.imagineDiscoverTypeFilter,
    allFilesType: state.imagineAllFilesTypeFilter,
    ids: renderItems.map((item) => item.id),
    selected: Array.from(state.selectedItems).sort(),
    busy: remoteBusy,
    partialTypeFill: hidePartialTypeFill,
  });
  if (
    renderItems.length
    && state.imagineRemoteRenderSignature === renderSignature
    && els.imagineGallery.dataset.filter === (allFilesView ? "imagine-all-files" : (discoverView ? "imagine-discover" : "imagine"))
    && els.imagineGallery.children.length
  ) {
    updateExistingCardSelection();
    setLoadingIndicator();
    applyImagineRemoteOrderedReveal();
    return;
  }
  state.imagineRemoteRenderSignature = renderSignature;
  if (!renderItems.length) {
    const loadingClass = remoteBusy ? " imagine-remote-loading" : "";
    els.imagineGallery.innerHTML = `<div class="empty-state${loadingClass}">${remoteBusy ? loadingLabel : emptyLabel}</div>`;
    return;
  }
  const existingCards = Array.from(els.imagineGallery.querySelectorAll(".card[data-item-id]"));
  const existingIds = existingCards.map((card) => card.dataset.itemId || "");
  const itemIds = renderItems.map((item) => item.id);
  const sameCards = existingIds.length === itemIds.length
    && existingIds.every((id, index) => id === itemIds[index]);
  if (sameCards) {
    updateExistingCardSelection();
    setLoadingIndicator();
    applyImagineRemoteOrderedReveal();
    return;
  }
  const canAppend = existingIds.length > 0
    && existingIds.length < itemIds.length
    && existingIds.every((id, index) => id === itemIds[index]);
  if (canAppend) {
    const additions = renderItems.slice(existingIds.length);
    const fragmentHost = document.createElement("div");
    fragmentHost.innerHTML = additions.map((item) => cardHtml(item)).join("");
    bindGalleryCardEvents(fragmentHost);
    while (fragmentHost.firstChild) {
      els.imagineGallery.appendChild(fragmentHost.firstChild);
    }
    updateExistingCardSelection();
    setLoadingIndicator();
    applyImagineRemoteOrderedReveal(fragmentHost);
    return;
  }
  els.imagineGallery.innerHTML = [
    ...renderItems.map((item) => cardHtml(item)),
    remoteBusy ? `<div class="empty-state imagine-remote-loading">${loadingLabel}</div>` : "",
  ].join("");
  bindGalleryCardEvents(els.imagineGallery);
  applyImagineRemoteOrderedReveal();
}

function maybeLoadNextImagineRemotePage(options = {}) {
  if (state.view !== "imagine-library" || state.imagineRemoteBusy || state.imagineRemoteComplete) return;
  if (!state.imagineRemoteLoadedOnce || !state.imagineRemoteCursor) return;
  if (Date.now() < Number(state.imagineRemoteSuppressAutoLoadUntil || 0)) return;
  const galleryScroller = els.imagineGallery && els.imagineGallery.scrollHeight > els.imagineGallery.clientHeight + 1
    ? els.imagineGallery
    : null;
  const distanceToBottom = galleryScroller
    ? galleryScroller.scrollHeight - (galleryScroller.scrollTop + galleryScroller.clientHeight)
    : document.documentElement.scrollHeight - (window.scrollY + window.innerHeight);
  const threshold = Number(options.threshold || 260);
  if (distanceToBottom > threshold) return;
  loadImagineRemoteLibrary({ automatic: true });
}

function handleImagineRemoteWheel(event) {
  if (state.view !== "imagine-library" || state.imagineRemoteView !== IMAGINE_REMOTE_VIEW_ALL_FILES) return;
  if (Number(event.deltaY || 0) <= 0) return;
  window.requestAnimationFrame(() => maybeLoadNextImagineRemotePage({ threshold: 520 }));
}

function updateGalleryJobOverlays() {
  const jobsById = new Map(state.jobs.map((job) => [String(job.id), job]));
  $$(".gallery-generation-overlay[data-job-id]").forEach((overlay) => {
    const job = jobsById.get(String(overlay.dataset.jobId || ""));
    const card = overlay.closest(".card");
    if (!job || !isRunningVisualJob(job)) {
      card?.classList.remove("is-generating");
      overlay.remove();
      return;
    }
    const progress = Math.max(1, jobProgress(job));
    const progressEl = overlay.querySelector(".gallery-generation-progress");
    if (progressEl) progressEl.textContent = `${progress}%`;
    card?.classList.add("is-generating");
  });
}

function updateDetailJobOverlays() {
  const jobsById = new Map(state.jobs.map((job) => [String(job.id), job]));
  $$(".detail-generation-progress[data-job-id]").forEach((progressEl) => {
    const job = jobsById.get(String(progressEl.dataset.jobId || ""));
    if (!job || !isRunningVisualJob(job)) return;
    progressEl.textContent = `Creating ${Math.max(1, jobProgress(job))}%`;
  });
  $$(".detail-job-thumb-progress[data-job-id]").forEach((progressEl) => {
    const job = jobsById.get(String(progressEl.dataset.jobId || ""));
    if (!job || !isRunningVisualJob(job)) return;
    progressEl.textContent = `${Math.max(1, jobProgress(job))}%`;
  });
}

function itemTokenProvider(item) {
  if (!item || !["image", "video"].includes(item.type)) return "";
  const metadata = item.metadata || {};
  const imagine = metadata.imagine || {};
  const explicit = String(
    item.token_source
      || metadata.token_source
      || item.provider
      || metadata.provider
      || "",
  ).toLowerCase();
  if (explicit.includes("imagine")) return "imagine";
  if (explicit.includes("build")) return "build";
  if (
    isImagineLineageItem(item)
      || metadata.imagine_post_id
      || metadata.imagine_video_post_id
      || metadata.imagine_media_url
      || metadata.imagine_video_media_url
      || imagine.post_id
  ) {
    return "imagine";
  }
  const mode = String(item.mode || metadata.mode || "").toLowerCase();
  if (item.source === "upload-card" || item.type === "upload-image" || mode === "upload") return "";
  if (
    mode.startsWith("image-")
      || mode.startsWith("video-")
      || metadata.model
      || item.request_id
  ) {
    return "build";
  }
  return "";
}

function thumbnailProviderBadgeHtml(item) {
  const provider = itemTokenProvider(item);
  if (!provider) return "";
  const label = provider === "imagine" ? "I" : "B";
  const title = provider === "imagine" ? "Imagine token" : "Build token";
  return `<span class="thumbnail-provider-badge thumbnail-provider-${escapeHtml(provider)}" title="${escapeHtml(title)}">${label}</span>`;
}

function thumbnailMetaHtml(item) {
  const providerBadge = thumbnailProviderBadgeHtml(item);
  const modelLabel = detailModelLabel(item);
  const videoIcon = item?.type === "video"
    ? '<span class="thumbnail-video-icon"><img src="/assets/icons/imagine/video.svg" alt="Video" /></span>'
    : "";
  const modelName = (modelLabel || videoIcon)
    ? `<span class="thumbnail-model-pill">${videoIcon}${modelLabel ? `<span class="thumbnail-model-name">${escapeHtml(modelLabel)}</span>` : ""}</span>`
    : "";
  if (!providerBadge && !modelName) return "";
  return `<div class="thumbnail-meta-row">${providerBadge}${modelName}</div>`;
}

function isRemoteDeletedItem(item) {
  const metadata = item?.metadata || {};
  const imagine = metadata.imagine || {};
  return Boolean(metadata.remote_deleted || metadata.is_deleted_remote || imagine.deleted || imagine.remote_deleted);
}

function remoteDeletedBadgeHtml(_item) {
  return "";
}

function cardHtml(item, visualJob = null) {
  const preview = previewHtml(item);
  const selected = state.selectedItems.has(item.id) ? " selected" : "";
  const generating = visualJob ? " is-generating" : "";
  const deleted = isRemoteDeletedItem(item) ? " is-remote-deleted" : "";
  const draggable = ["image", "video"].includes(item.type) && item.local_url ? "true" : "false";
  const displayTitle = item.type === "video" ? "Video" : "Image";
  const thumbnailMeta = thumbnailMetaHtml(item);
  const selectButton = state.view === "imagine-library"
    ? `<button class="item-select media-card-select-button" type="button" data-id="${escapeHtml(item.id)}" aria-label="Select ${escapeHtml(displayTitle)}" aria-pressed="${state.selectedItems.has(item.id) ? "true" : "false"}"><span class="selection-checkmark" aria-hidden="true">∨</span></button>`
    : "";
  if (item.type === "prompt") {
    return `<article class="card prompt-card${selected}" draggable="false" data-item-id="${escapeHtml(item.id)}" data-item-type="prompt">
      <div class="prompt-card-head">
        <div class="card-title" title="${escapeHtml(item.title || "Prompt")}">${escapeHtml(item.title || "Prompt")}</div>
      </div>
      <button class="prompt-card-open" type="button" data-id="${escapeHtml(item.id)}">
        <span>${escapeHtml(item.prompt || "Saved prompt")}</span>
      </button>
      <div class="card-body">
        ${cardActionsHtml(item)}
      </div>
    </article>`;
  }
  return `<article class="card${selected}${generating}${deleted}" draggable="${draggable}" data-item-id="${escapeHtml(item.id)}" data-item-type="${escapeHtml(item.type)}">
    <button class="preview media-card-open" type="button" data-id="${escapeHtml(item.id)}" aria-label="Open ${escapeHtml(displayTitle)}">${preview}${remoteDeletedBadgeHtml(item)}${visualJob ? galleryJobOverlayHtml(visualJob) : ""}</button>
    ${thumbnailMeta}
    ${selectButton}
    ${mediaCardActionsHtml(item)}
  </article>`;
}

function galleryJobCardHtml(job) {
  const context = jobContext(job);
  const targetType = visualJobTargetType(job);
  const previewUrl = context.preview_url || "";
  const item = {
    id: `job-card-${job.id}`,
    type: targetType,
    local_url: previewUrl,
    prompt: job.prompt || "",
    title: "Creating",
  };
  const jobMeta = targetType === "video"
    ? '<div class="thumbnail-meta-row"><span class="thumbnail-model-pill"><span class="thumbnail-video-icon"><img src="/assets/icons/imagine/video.svg" alt="Video" /></span></span></div>'
    : "";
  return `<article class="card is-generating gallery-job-card" draggable="false" data-job-id="${escapeHtml(job.id)}" data-item-type="${escapeHtml(targetType)}">
    <div class="preview">${previewHtml(item)}${galleryJobOverlayHtml(job)}</div>
    ${jobMeta}
  </article>`;
}

function cardActionsHtml(item) {
  const copy = `<button class="copy-prompt-btn" type="button" data-copy="${escapeHtml(item.prompt || "")}">Copy Prompt</button>`;
  if (item.type === "image") {
    const toVideo = item.local_url
      ? `<button class="to-video-card-btn" type="button" data-id="${escapeHtml(item.id)}">To Video</button>`
      : `<button type="button" disabled>No file</button>`;
    return `<div class="card-actions">${toVideo}${copy}</div>`;
  }
  if (item.type === "video") {
    const extend = item.local_url
      ? `<button class="extend-card-btn" type="button" data-id="${escapeHtml(item.id)}">Extend</button>`
      : `<button type="button" disabled>No file</button>`;
    return `<div class="card-actions">${extend}${copy}</div>`;
  }
  return `<div class="card-actions prompt-card-actions">
    <button class="copy-prompt-btn prompt-copy-button" type="button" data-copy="${escapeHtml(item.prompt || "")}">Copy</button>
    <button class="delete-card-btn prompt-delete-button" type="button" data-id="${escapeHtml(item.id)}">Delete</button>
  </div>`;
}

function mediaCardActionsHtml(item) {
  const disabled = item.local_url ? "" : " disabled";
  const remoteImagine = isImagineRemoteItem(item);
  const moveClasses = remoteImagine
    ? "move-card-btn media-card-move-button media-card-delete-button"
    : "move-card-btn media-card-move-button";
  const move = `<button class="${moveClasses}" type="button" data-id="${escapeHtml(item.id)}" aria-label="Move to Gallery"><span class="media-card-action-glyph" aria-hidden="true">↗</span></button>`;
  if (remoteImagine) {
    return `<div class="card-actions media-card-actions">
      <button class="download-card-btn media-card-download-button" type="button" data-id="${escapeHtml(item.id)}" aria-label="Download"${disabled}><span class="media-card-action-glyph media-card-download-glyph" aria-hidden="true">↓</span></button>
      ${move}
    </div>`;
  }
  return `<div class="card-actions media-card-actions">
    <button class="download-card-btn media-card-download-button" type="button" data-id="${escapeHtml(item.id)}" aria-label="Download"${disabled}><span class="media-card-action-glyph media-card-download-glyph" aria-hidden="true">↓</span></button>
    ${move}
    <button class="delete-card-btn danger-card-btn media-card-delete-button" type="button" data-id="${escapeHtml(item.id)}" aria-label="Delete"><span class="media-card-action-glyph media-card-delete-glyph delete-x-icon" aria-hidden="true"></span></button>
  </div>`;
}

function shouldUseLocalOrderedReveal(item) {
  const query = els.searchInput?.value.trim() || "";
  return Boolean(
    item
      && state.view === "gallery"
      && !query
      && ["all", "video", "image"].includes(state.filter)
      && ["image", "video"].includes(item.type)
      && item.local_url
      && !isImagineRemoteItem(item)
      && !String(item.id || "").startsWith("job-card-"),
  );
}

function orderedMediaClassFor(item) {
  if (isImagineRemoteItem(item)) return "imagine-remote-ordered-media";
  if (shouldUseLocalOrderedReveal(item)) return "local-ordered-media";
  return "";
}

function previewHtml(item) {
  const orderedClass = orderedMediaClassFor(item);
  const orderedClassAttr = orderedClass ? ` class="${orderedClass}"` : "";
  if (item.type === "image" && item.local_url) {
    return `<img${orderedClassAttr} src="${escapeHtml(item.local_url)}" alt="${escapeHtml(item.prompt || "Generated image")}" loading="lazy" />`;
  }
  if (item.type === "video" && item.local_url) {
    const videoClass = orderedClass ? `gallery-hover-video ${orderedClass}` : "gallery-hover-video";
    return `<video class="${videoClass}" src="${escapeHtml(item.local_url)}" muted playsinline preload="metadata"></video>`;
  }
  const label = item.type === "video" ? "Video" : item.type === "image" ? "Image" : "Saved prompt";
  return `<div class="prompt-preview"><span>${escapeHtml(item.prompt || label)}</span></div>`;
}

function videoPosterUrlFor(item) {
  if (!item || item.type !== "video") return "";
  const metadata = item.metadata || {};
  const imagine = metadata.imagine || {};
  const directCandidates = [
    metadata.poster_url,
    metadata.primary_poster_url,
    imagine.poster_url,
    imagine.primary_poster_url,
    metadata.start_image,
  ];
  for (const value of directCandidates) {
    const url = sourceReferenceUrl(value);
    if (url) return url;
  }
  return "";
}

function videoPosterAttr(item) {
  const poster = videoPosterUrlFor(item);
  return poster ? ` poster="${escapeHtml(poster)}"` : "";
}

function applyOrderedMediaReveal(gallery, selector, options = {}) {
  if (!gallery) return;
  const readyKey = options.readyKey || "orderedReady";
  const observedKey = options.observedKey || "orderedObserved";
  const medias = Array.from(gallery.querySelectorAll(selector));
  if (!medias.length) return;
  const revealReadyPrefix = () => {
    for (const media of medias) {
      if (media.dataset[readyKey] !== "1" && media.dataset[readyKey] !== "error") break;
      media.classList.add("is-visible");
    }
  };
  medias.forEach((media) => {
    if (media.dataset[observedKey] === "1") return;
    media.dataset[observedKey] = "1";
    if (media.tagName === "IMG") {
      if (media.complete) {
        media.dataset[readyKey] = media.naturalWidth ? "1" : "error";
        revealReadyPrefix();
      } else {
        media.addEventListener("load", () => {
          media.dataset[readyKey] = "1";
          revealReadyPrefix();
        }, { once: true });
        media.addEventListener("error", () => {
          media.dataset[readyKey] = "error";
          revealReadyPrefix();
        }, { once: true });
      }
      return;
    }
    if (media.readyState >= 1) {
      media.dataset[readyKey] = "1";
      revealReadyPrefix();
    } else {
      media.addEventListener("loadedmetadata", () => {
        media.dataset[readyKey] = "1";
        revealReadyPrefix();
      }, { once: true });
      media.addEventListener("error", () => {
        media.dataset[readyKey] = "error";
        revealReadyPrefix();
      }, { once: true });
    }
  });
  revealReadyPrefix();
}

function applyImagineRemoteOrderedReveal(root = document) {
  const gallery = els.imagineGallery;
  if (!gallery || state.view !== "imagine-library") return;
  applyOrderedMediaReveal(gallery, ".imagine-remote-ordered-media", {
    readyKey: "remoteReady",
    observedKey: "remoteObserved",
  });
}

function applyLocalGalleryOrderedReveal() {
  if (!els.gallery || state.view !== "gallery") return;
  applyOrderedMediaReveal(els.gallery, ".local-ordered-media", {
    readyKey: "localReady",
    observedKey: "localObserved",
  });
}

function dotCssOverlayHtml(extraClass = "") {
  const className = extraClass ? ` ${extraClass}` : "";
  return `<span class="dot-css-overlay${className}" aria-hidden="true">
    <span class="dot-css-orb dot-css-orb-one"></span>
    <span class="dot-css-orb dot-css-orb-two"></span>
    <span class="dot-css-shimmer dot-css-shimmer-one"></span>
    <span class="dot-css-shimmer dot-css-shimmer-two"></span>
    <span class="dot-css-shimmer dot-css-shimmer-three"></span>
  </span>`;
}

function galleryJobOverlayHtml(job) {
  const progress = Math.max(1, jobProgress(job));
  return `<span class="gallery-generation-overlay" data-job-id="${escapeHtml(job.id)}">
    ${dotCssOverlayHtml("gallery-dot-css")}
    <span class="gallery-generation-progress">${progress}%</span>
  </span>`;
}

function bindGalleryPreviewVideos(root = document) {
  Array.from((root || document).querySelectorAll(".gallery-hover-video")).forEach((video) => {
    if (video.dataset.hoverBound === "1") return;
    video.dataset.hoverBound = "1";
    const card = video.closest(".card");
    if (!card) return;
    const previewStack = video.closest(".video-preview-stack");
    card.addEventListener("mouseenter", () => {
      video.muted = true;
      previewStack?.classList.add("is-playing");
      video.play().catch(() => {});
    });
    card.addEventListener("mouseleave", () => {
      video.pause();
      previewStack?.classList.remove("is-playing");
      try {
        video.currentTime = 0;
      } catch {
        // Some browsers refuse seeking before metadata, harmless for hover preview.
      }
      if (video.getAttribute("poster")) {
        video.load();
      }
    });
  });
}

function toggleSelectedItem(itemId) {
  if (!itemId) return;
  if (state.selectedItems.has(itemId)) state.selectedItems.delete(itemId);
  else state.selectedItems.add(itemId);
}

function renderCurrentCardGallery() {
  if (state.view === "imagine-library") renderImagineLibrary();
  else renderGallery();
}

function bindCardSelectionControls(root = document) {
  Array.from((root || document).querySelectorAll(".item-select")).forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const itemId = button.dataset.id || "";
      toggleSelectedItem(itemId);
      if (state.view === "imagine-library" && !state.selectedItems.has(itemId)) {
        button.blur();
      }
      renderCurrentCardGallery();
    });
  });
}

function resetVideosIn(root) {
  if (!root) return;
  root.querySelectorAll("video").forEach((video) => {
    video.pause();
    try {
      video.currentTime = 0;
    } catch {
      // Some browsers reject seeking before metadata is ready.
    }
  });
}

function workspaceHistoryUrl(options = {}) {
  const url = new URL(window.location.href);
  url.searchParams.delete("detail");
  if (state.workspaceFolderId) url.searchParams.set("folder", state.workspaceFolderId);
  else url.searchParams.delete("folder");
  if (options.folderGallery) url.searchParams.set("gallery", "1");
  else url.searchParams.delete("gallery");
  if (options.imagineLibrary) {
    url.searchParams.set("imagine", "1");
    const imagineRemoteView = normalizeImagineRemoteView(options.imagineRemoteView || state.imagineRemoteView);
    if (imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES) {
      url.searchParams.set("imagine_view", IMAGINE_REMOTE_VIEW_ALL_FILES);
      const allFilesType = normalizeImagineAllFilesTypeFilter(options.imagineAllFilesType !== undefined ? options.imagineAllFilesType : state.imagineAllFilesTypeFilter);
      if (allFilesType === IMAGINE_ALL_FILES_TYPE_ALL) url.searchParams.delete("imagine_all_files_type");
      else url.searchParams.set("imagine_all_files_type", allFilesType);
      url.searchParams.delete("imagine_portfolio_type");
      url.searchParams.delete("imagine_discover_type");
      url.searchParams.delete("imagine_type");
    } else if (imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER) {
      url.searchParams.set("imagine_view", IMAGINE_REMOTE_VIEW_DISCOVER);
      const discoverType = normalizeImagineDiscoverTypeFilter(options.imagineDiscoverType !== undefined ? options.imagineDiscoverType : state.imagineDiscoverTypeFilter);
      if (discoverType === IMAGINE_DISCOVER_TYPE_ALL) url.searchParams.delete("imagine_discover_type");
      else url.searchParams.set("imagine_discover_type", discoverType);
      url.searchParams.delete("imagine_portfolio_type");
      url.searchParams.delete("imagine_all_files_type");
      url.searchParams.delete("imagine_type");
    } else {
      url.searchParams.delete("imagine_view");
      const portfolioType = normalizeImaginePortfolioTypeFilter(options.imaginePortfolioType !== undefined ? options.imaginePortfolioType : state.imaginePortfolioTypeFilter);
      if (portfolioType === IMAGINE_PORTFOLIO_TYPE_ALL) url.searchParams.delete("imagine_portfolio_type");
      else url.searchParams.set("imagine_portfolio_type", portfolioType);
      url.searchParams.delete("imagine_discover_type");
      url.searchParams.delete("imagine_all_files_type");
      url.searchParams.delete("imagine_type");
    }
  } else {
    url.searchParams.delete("imagine");
    url.searchParams.delete("imagine_view");
    url.searchParams.delete("imagine_portfolio_type");
    url.searchParams.delete("imagine_discover_type");
    url.searchParams.delete("imagine_all_files_type");
    url.searchParams.delete("imagine_type");
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

function replaceImagineLibraryHistory() {
  if (state.view !== "imagine-library") return;
  history.replaceState(
    {
      ...history.state,
      grokStudioView: "imagine-library",
      detailItemId: "",
      workspaceFolderId: "",
      imagineRemoteView: state.imagineRemoteView,
      imaginePortfolioTypeFilter: state.imaginePortfolioTypeFilter,
      imagineDiscoverTypeFilter: state.imagineDiscoverTypeFilter,
      imagineAllFilesTypeFilter: state.imagineAllFilesTypeFilter,
    },
    "",
    workspaceHistoryUrl({
      imagineLibrary: true,
      imagineRemoteView: state.imagineRemoteView,
      imaginePortfolioType: state.imaginePortfolioTypeFilter,
      imagineDiscoverType: state.imagineDiscoverTypeFilter,
      imagineAllFilesType: state.imagineAllFilesTypeFilter,
    }),
  );
}

function detailHistoryUrl(itemId = "") {
  const url = new URL(workspaceHistoryUrl(), window.location.origin);
  if (itemId) url.searchParams.set("detail", itemId);
  else url.searchParams.delete("detail");
  return `${url.pathname}${url.search}${url.hash}`;
}

function replaceDetailHistory(itemId) {
  if (!itemId) return;
  history.replaceState(
    {
      ...history.state,
      grokStudioView: "detail",
      detailItemId: itemId,
      detailNavView: state.detailNavView,
      detailNavFilter: state.detailNavFilter,
      workspaceFolderId: state.workspaceFolderId,
    },
    "",
    detailHistoryUrl(itemId),
  );
}

function openDetail(itemId, options = {}) {
  const requested = galleryItemById(itemId);
  const item = detailInitialItem(requested);
  if (!item || !["image", "video"].includes(item.type)) return;
  const wasDetail = state.view === "detail";
  setDetailNavContext(options.navContext || detailNavContextFromCurrentView());
  state.view = "detail";
  state.detailItemId = item.id;
  state.detailSelectedSourceUrl = "";
  state.detailSelectedJobId = "";
  state.detailThumbScrollTop = 0;
  state.detailExtend = false;
  state.detailExtendStart = 0;
  syncWorkspaceView();
  els.promptInput.value = item.prompt || "";
  autoSizePromptInput();
  syncComposerToDetailItem(item, options.mode);
  document.querySelector(".workspace")?.classList.add("show-detail");
  if (els.detailScreen) els.detailScreen.hidden = false;
  state.selectedItems.clear();
  renderGallery();
  renderDetail();
  if (!options.fromHistory) {
    const method = wasDetail ? "replaceState" : "pushState";
    history[method](
      {
        ...history.state,
        grokStudioView: "detail",
        detailItemId: item.id,
        detailNavView: state.detailNavView,
        detailNavFilter: state.detailNavFilter,
        workspaceFolderId: state.workspaceFolderId,
      },
      "",
      detailHistoryUrl(item.id),
    );
  }
}

function resetComposerAfterDetail() {
  els.promptInput.value = "";
  autoSizePromptInput();
  state.editImages.forEach(revokeImageSource);
  state.referenceImages.forEach(revokeImageSource);
  state.editImages = [];
  state.referenceImages = [];
  clearStartImage();
  clearSourceVideo();
  state.attachmentTrayOpen = false;
  els.imageFiles.value = "";
  els.referenceImageFiles.value = "";
  renderImageFileNames();
  renderVideoFileNames();
  renderAttachmentTray();
}

function closeDetail(options = {}) {
  const wasDetail = state.view === "detail";
  const shouldGoBack = !options.fromHistory
    && !options.returnToWorkspace
    && history.state?.grokStudioView === "detail";
  resetVideosIn(els.detailScreen);
  state.view = "gallery";
  state.detailItemId = "";
  state.detailSelectedSourceUrl = "";
  state.detailSelectedJobId = "";
  state.detailThumbScrollTop = 0;
  state.detailExtend = false;
  state.detailExtendStart = 0;
  if (wasDetail) resetComposerAfterDetail();
  document.querySelector(".workspace")?.classList.remove("show-detail");
  syncWorkspaceView();
  if (els.detailScreen) els.detailScreen.hidden = true;
  renderGallery();
  if (shouldGoBack) {
    history.back();
  } else if (!options.fromHistory) {
    history.replaceState(
      { ...history.state, grokStudioView: "gallery", detailItemId: "", workspaceFolderId: state.workspaceFolderId },
      "",
      detailHistoryUrl(),
    );
  }
}

function closeDetailToWorkspace() {
  closeDetail({ returnToWorkspace: true });
}

function detailItem() {
  return galleryItemById(state.detailItemId);
}

function renderDetail() {
  if (!els.detailScreen) return;
  const item = detailItem();
  if (state.view !== "detail" || !item) {
    els.detailScreen.hidden = true;
    document.querySelector(".workspace")?.classList.remove("show-detail");
    return;
  }
  const workspace = document.querySelector(".workspace");
  workspace?.classList.add("show-detail");
  workspace?.classList.remove("show-folder-gallery");
  if (els.folderGalleryScreen) els.folderGalleryScreen.hidden = true;
  els.detailScreen.hidden = false;
  els.detailScreen.classList.toggle("detail-extend-active", state.detailExtend);
  const versions = detailThumbVersionsFor(item);
  const displayItem = detailDisplayItem(item);
  const visualJob = detailPrimaryVisualJob(item);
  const visualThumbJobs = detailVisualJobs(item).slice(0, 4);
  const detailThumbCount = versions.length + visualThumbJobs.length;
  const regularMedia = displayItem.type === "video"
    ? videoPlayerHtml(displayItem.local_url, "Video", {
      compact: false,
      extraClass: "detail-video-player",
      poster: videoPosterUrlFor(displayItem),
    })
    : `<img class="detail-image" src="${escapeHtml(displayItem.local_url)}" alt="${escapeHtml(displayItem.prompt || displayItem.title || "Image")}" draggable="false" />`;
  const media = visualJob ? detailGenerationMediaHtml(visualJob, displayItem) : regularMedia;
  const editAction = ["image", "video"].includes(displayItem.type) && !visualJob
    ? '<button class="detail-action edit-detail" type="button" aria-label="Edit image"><span class="detail-edit-glyph" aria-hidden="true">e</span></button>'
    : "";
  const detailActions = isImagineRemoteItem(item)
    ? `${editAction}
          <button class="detail-action move-detail" type="button" aria-label="Move to Gallery"><span class="media-card-action-glyph" aria-hidden="true">↗</span></button>
          <button class="detail-action download-detail" type="button" aria-label="Download">↓</button>`
    : `${editAction}
          <button class="detail-action move-detail" type="button" aria-label="Move to Gallery"><span class="media-card-action-glyph" aria-hidden="true">↗</span></button>
          <button class="detail-action download-detail" type="button" aria-label="Download">↓</button>
          <button class="detail-action delete-detail" type="button" aria-label="Delete"><span class="delete-x-icon" aria-hidden="true"></span></button>`;
  els.detailScreen.innerHTML = `
    <section class="detail-stage ${displayItem.type === "video" ? "is-video" : "is-image"}${visualJob ? " has-generation" : ""}">
      <div class="detail-media-shell">
        <aside class="detail-stack${detailThumbCount > 10 ? " is-scrollable" : ""}" aria-label="Versions">
          ${versions.map((version) => detailThumbHtml(
            version,
            version.type === "source"
              ? version.local_url === state.detailSelectedSourceUrl
              : !visualJob
                && !state.detailSelectedSourceUrl
                && mediaItemIdentity(version) === mediaItemIdentity(item),
          )).join("")}
          ${visualThumbJobs.map((job) => detailJobThumbHtml(
            job,
            displayItem,
            visualJob?.id === job.id || state.detailSelectedJobId === job.id,
          )).join("")}
        </aside>
        <div class="detail-media-wrap">${detailMetaHtml(displayItem)}${media}${remoteDeletedBadgeHtml(displayItem)}${detailJobBadgesHtml(item)}</div>
        <aside class="detail-actions" aria-label="Actions">
          ${detailActions}
        </aside>
      </div>
    </section>
    <div class="detail-prompt-pill" title="${escapeHtml(item.prompt || "")}">
      <span>${escapeHtml(item.prompt || "")}</span>
    </div>
  `;
  restoreDetailThumbScroll();
  bindDetailEvents(item, displayItem);
  bindCustomVideoPlayers();
  bindDetailMediaAspect();
  bindJobButtons();
  if (displayItem.type === "video") {
    const video = els.detailScreen.querySelector(".detail-video-player .custom-video");
    const player = video?.closest("[data-video-player]");
    if (video) {
      video.loop = true;
      video.muted = false;
      video.removeAttribute("title");
      player?.classList.add("controls-hidden");
    }
    if (video && state.detailExtend) {
      const applyExtendFrame = () => {
        video.currentTime = state.detailExtendStart || 0;
        video.pause();
        refreshDetailExtendTimeLabel();
      };
      if (Number.isFinite(video.duration) && video.duration > 0) applyExtendFrame();
      else video.addEventListener("loadedmetadata", applyExtendFrame, { once: true });
    } else if (video) {
      video.play().catch(() => {});
    }
  }
}

function bindDetailMediaAspect() {
  const shell = els.detailScreen?.querySelector(".detail-media-shell");
  const stage = shell?.closest(".detail-stage");
  const media = shell?.querySelector(".detail-image, .detail-video-player .custom-video, .detail-generation-media");
  if (!shell || !stage || !media) return;
  const detailPlayer = media instanceof HTMLVideoElement ? media.closest(".detail-video-player") : null;
  if (detailPlayer) stage.classList.add("is-sizing");
  const syncAspect = () => {
    const width = media instanceof HTMLVideoElement ? media.videoWidth : media.naturalWidth;
    const height = media instanceof HTMLVideoElement ? media.videoHeight : media.naturalHeight;
    if (!width || !height) return;
    const aspect = width / height;
    const sideReserve = window.innerWidth <= 980 ? 0 : 180;
    const maxWidth = Math.max(240, stage.clientWidth - sideReserve);
    const maxHeight = Math.max(180, Math.min(stage.clientHeight, 740, window.innerHeight - 190));
    const fittedWidth = Math.min(maxWidth, maxHeight * aspect);
    const fittedHeight = fittedWidth / aspect;
    shell.style.setProperty("--detail-media-aspect", `${width} / ${height}`);
    shell.style.maxWidth = "none";
    shell.style.width = `${fittedWidth}px`;
    shell.style.height = `${fittedHeight}px`;
    media.closest(".detail-video-player")?.style.setProperty("--detail-media-aspect", `${width} / ${height}`);
    if (detailPlayer) stage.classList.remove("is-sizing");
  };
  syncAspect();
  media.addEventListener(media instanceof HTMLVideoElement ? "loadedmetadata" : "load", syncAspect, { once: true });
  new ResizeObserver(syncAspect).observe(stage);
}

function detailThumbHtml(item, active) {
  const src = item.local_url || "";
  const media = item.type === "video"
    ? `<video src="${escapeHtml(src)}" muted playsinline preload="metadata"${videoPosterAttr(item)}></video><span class="detail-thumb-type"><img src="/assets/icons/imagine/video.svg" alt="" /></span>`
    : `<img src="${escapeHtml(src)}" alt="" />`;
  if (item.type === "source") {
    return `<button class="detail-thumb is-source${active ? " active" : ""}" type="button" data-source-url="${escapeHtml(src)}" title="${escapeHtml(item.title || "Original Image")}">${media}</button>`;
  }
  return `<button class="detail-thumb ${item.type === "video" ? "is-video" : "is-image"}${active ? " active" : ""}" type="button" data-id="${escapeHtml(item.id)}">${media}</button>`;
}

function detailModelLabel(item) {
  if (!item || !["image", "video"].includes(item.type)) return "";
  const model = String(item.metadata?.model || item.model || "").toLowerCase();
  if (item.type === "video") {
    if (!model) return "Model 1.0";
    if (model.includes("1.5-preview")) return "Model 1.5p";
    if (model.includes("1.5")) return "Model 1.5";
    if (model.includes("grok-imagine-video")) return "Model 1.0";
    return "";
  }
  if (model.includes("quality")) return "Quality";
  if (model.includes("grok-imagine-image")) return "Speed";
  return "";
}

function detailModelBadgeHtml(item) {
  const label = detailModelLabel(item);
  const videoIcon = item?.type === "video"
    ? '<span class="detail-video-icon"><img src="/assets/icons/imagine/video.svg" alt="Video" /></span>'
    : "";
  if (!label && !videoIcon) return "";
  return `<span class="detail-model-badge">${videoIcon}${label ? `<span class="detail-model-name">${escapeHtml(label)}</span>` : ""}</span>`;
}

function detailProviderBadgeHtml(item) {
  const provider = itemTokenProvider(item);
  if (!provider) return "";
  const label = provider === "imagine" ? "I" : "B";
  const title = provider === "imagine" ? "Imagine token" : "Build token";
  return `<span class="detail-provider-badge detail-provider-${escapeHtml(provider)}" title="${escapeHtml(title)}">${label}</span>`;
}

function detailMetaHtml(item) {
  const providerBadge = detailProviderBadgeHtml(item);
  const modelBadge = detailModelBadgeHtml(item);
  if (!providerBadge && !modelBadge) return "";
  return `<div class="detail-meta-row">${providerBadge}${modelBadge}</div>`;
}

function captureDetailThumbScroll() {
  const stack = els.detailScreen?.querySelector(".detail-stack");
  state.detailThumbScrollTop = stack ? stack.scrollTop : 0;
}

function restoreDetailThumbScroll() {
  const stack = els.detailScreen?.querySelector(".detail-stack");
  if (!stack) return;
  const scrollTop = Math.max(0, Number(state.detailThumbScrollTop || 0));
  stack.scrollTop = scrollTop;
  requestAnimationFrame(() => {
    stack.scrollTop = scrollTop;
  });
}

function bindDetailEvents(item, displayItem = item) {
  els.detailScreen.querySelector(".detail-stage")?.addEventListener("click", handleDetailExtendBlankClick);
  els.detailScreen.querySelector(".detail-image")?.addEventListener("click", toggleDetailImageFullscreen);
  els.detailScreen.querySelectorAll(".detail-thumb").forEach((button) => {
    button.addEventListener("click", () => {
      captureDetailThumbScroll();
      if (button.dataset.jobId) {
        const job = state.jobs.find((candidate) => candidate.id === button.dataset.jobId);
        if (state.detailSelectedJobId === button.dataset.jobId && job?.status !== "failed") return;
        const deselectFailedJob = job?.status === "failed" && state.detailSelectedJobId === job.id;
        state.detailSelectedJobId = deselectFailedJob ? "media" : button.dataset.jobId;
        if (deselectFailedJob) {
          els.promptInput.value = item.prompt || "";
          autoSizePromptInput();
          syncComposerToDetailItem(item);
        } else if (job?.prompt) {
          els.promptInput.value = job.prompt;
          autoSizePromptInput();
        }
        clearDetailExtendState();
        renderDetail();
        return;
      }
      if (button.dataset.sourceUrl) {
        if (state.detailSelectedSourceUrl === button.dataset.sourceUrl && state.detailSelectedJobId === "media") return;
        selectDetailSource(button.dataset.sourceUrl);
        return;
      }
      if (
        button.dataset.id === state.detailItemId
        && !state.detailSelectedSourceUrl
        && state.detailSelectedJobId === "media"
      ) return;
      state.detailItemId = button.dataset.id || state.detailItemId;
      replaceDetailHistory(state.detailItemId);
      state.detailSelectedSourceUrl = "";
      state.detailSelectedJobId = "media";
      clearDetailExtendState();
      const next = detailItem();
      if (next) {
        els.promptInput.value = next.prompt || "";
        autoSizePromptInput();
        syncComposerToDetailItem(next);
      }
      renderDetail();
    });
  });
  els.detailScreen.querySelector(".move-detail")?.addEventListener("click", () => {
    openMoveToGalleryDialog([item.id], { singleRemote: isImagineRemoteItem(item) });
  });
  els.detailScreen.querySelector(".edit-detail")?.addEventListener("click", () => openImageEditor(item, displayItem));
  els.detailScreen.querySelector(".download-detail")?.addEventListener("click", () => downloadItem(displayItem));
  els.detailScreen.querySelector(".delete-detail")?.addEventListener("click", () => {
    deleteDetailItem(item, displayItem).catch((error) => toastError(error.message));
  });
  els.detailScreen.querySelector(".detail-prompt-pill")?.addEventListener("click", () => {
    els.promptInput.value = item.prompt || "";
    autoSizePromptInput();
    els.promptInput.focus();
  });
}

function selectDetailSource(url) {
  const item = detailItem();
  if (!item || !url) return;
  state.detailSelectedSourceUrl = url;
  state.detailSelectedJobId = "media";
  syncSelectedDetailSourceForMode();
  renderDetail();
}

function syncSelectedDetailSourceForMode() {
  const source = selectedDetailSource();
  if (!source) return;
  if (state.mode === "image") {
    setEditImageFromDetailSource(source);
    return;
  }
  if (state.mode === "video") {
    setStartImageFromDetailSource(source);
    return;
  }
}

function syncComposerToDetailItem(item, preferredMode) {
  if (!item) return;
  setMode(preferredMode || "video");
}

function downloadItem(item) {
  if (!item?.local_url) return;
  const anchor = document.createElement("a");
  anchor.href = item.local_url;
  anchor.download = downloadName(item);
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}

function downloadItems(items) {
  uniqueDownloadItems(items).forEach((item, index) => {
    window.setTimeout(() => downloadItem(item), index * 120);
  });
}

function downloadRelatedItems(item) {
  downloadItems(relatedDownloadItemsFor(item));
}

function relatedDownloadItemsFor(item) {
  if (!item?.local_url) return [];
  const candidates = ["image", "video"].includes(item.type) ? groupItemsFor(item) : [item];
  return uniqueDownloadItems(candidates.filter((candidate) => candidate?.local_url));
}

function uniqueDownloadItems(items) {
  const unique = new Map();
  (items || []).forEach((item) => {
    if (!item?.local_url) return;
    const key = item.id || item.local_url;
    if (!unique.has(key)) unique.set(key, item);
  });
  return Array.from(unique.values());
}

function openImageEditor(item, displayItem = item) {
  const target = imageEditorTarget(item, displayItem);
  if (!target) {
    toastError("This video does not have a source image to edit.");
    return;
  }
  const url = new URL("/editor.html", window.location.origin);
  url.searchParams.set("item_id", target.itemId);
  url.searchParams.set("source", target.localUrl);
  url.searchParams.set("name", target.title || "Image");
  url.searchParams.set("return", detailHistoryUrl(item.id));
  sessionStorage.setItem(INTERNAL_EDITOR_NAV_KEY, "1");
  rememberImageEditorReturnContext();
  window.location.replace(url.toString());
}

function libraryImageByUrl(url) {
  const identity = mediaUrlKeys(url);
  return state.items.find((candidate) => (
    candidate.type === "image"
      && mediaUrlKeys(candidate.local_url).some((key) => identity.includes(key))
  )) || null;
}

function videoSourceImage(item) {
  const metadata = item?.metadata && typeof item.metadata === "object" ? item.metadata : {};
  const references = [
    metadata.start_image,
    ...(Array.isArray(metadata.reference_images) ? metadata.reference_images : []),
    ...(Array.isArray(metadata.source_images) ? metadata.source_images : []),
  ];
  for (const reference of references) {
    const localUrl = sourceReferenceUrl(reference);
    if (!localUrl) continue;
    const libraryItem = libraryImageByUrl(localUrl);
    return {
      itemId: libraryItem?.id || item.id,
      localUrl,
      title: libraryItem?.title || "Video Source Image",
    };
  }
  const related = latestGroupItemOfType(item, "image");
  if (!related?.local_url) return null;
  return {
    itemId: related.id,
    localUrl: related.local_url,
    title: related.title || "Video Source Image",
  };
}

function imageEditorTarget(item, displayItem = item) {
  if (!item?.id) return null;
  if (displayItem?.type === "image" && displayItem.local_url) {
    const libraryItem = libraryImageByUrl(displayItem.local_url);
    return {
      itemId: libraryItem?.id || item.id,
      localUrl: displayItem.local_url,
      title: libraryItem?.title || displayItem.title || item.title || "Image",
    };
  }
  if (displayItem?.type === "video") return videoSourceImage(item);
  return null;
}

async function handleImageEditorMessage(event) {
  if (event.origin !== window.location.origin || event.data?.type !== "grok-studio-image-edit-saved") return;
  await handleImageEditorSavedItem(String(event.data.itemId || ""));
}

async function handleImageEditorSavedItem(itemId) {
  if (!itemId) return;
  await loadState();
  if (!galleryItemById(itemId)) return;
  openDetail(itemId, { fromHistory: true });
  state.detailSelectedSourceUrl = "";
  state.detailSelectedJobId = "media";
  replaceDetailHistory(itemId);
  renderDetail();
}

async function consumeImageEditorReturn() {
  sessionStorage.removeItem(INTERNAL_EDITOR_NAV_KEY);
  const itemId = sessionStorage.getItem(IMAGE_EDITOR_SAVED_KEY) || "";
  if (!itemId) return;
  sessionStorage.removeItem(IMAGE_EDITOR_SAVED_KEY);
  await handleImageEditorSavedItem(itemId);
}

function toggleDetailImageFullscreen(event) {
  const image = event.currentTarget;
  if (!(image instanceof Element)) return;
  event.preventDefault();
  event.stopPropagation();
  openDetailImageFullscreen(image.getAttribute("src") || "");
}

function openDetailImageFullscreen(src) {
  if (!src) return;
  closeImagePreview();
  const overlay = document.createElement("div");
  overlay.className = "image-preview-overlay detail-image-fullscreen-overlay";
  overlay.innerHTML = `
    <div class="image-preview-modal detail-image-fullscreen-modal" role="dialog" aria-modal="true" aria-label="Image fullscreen">
      <img src="${escapeHtml(src)}" alt="" draggable="false" />
    </div>
  `;
  document.body.append(overlay);
  state.previewOverlay = overlay;
  overlay.addEventListener("click", closeImagePreview);
  const handleFullscreenChange = () => {
    if (state.previewOverlay === overlay && document.fullscreenElement !== overlay) {
      closeImagePreview({ skipExitFullscreen: true });
    }
  };
  overlay._fullscreenChangeHandler = handleFullscreenChange;
  document.addEventListener("fullscreenchange", handleFullscreenChange);
  const fullscreenRequest = overlay.requestFullscreen?.();
  fullscreenRequest?.catch?.(() => {});
}

async function deleteDetailItem(item, displayItem = item) {
  const selectedJob = selectedDetailJob(item);
  if (selectedJob) {
    const ok = await openGalleryActionDialog({
      title: "Delete thumbnail",
      message: "Delete this selected thumbnail?",
      confirmLabel: "Delete",
    });
    if (!ok) return;
    await api(`/api/jobs/${selectedJob.id}/dismiss`, { method: "POST", body: "{}" });
    state.jobs = state.jobs.filter((candidate) => candidate.id !== selectedJob.id);
    state.detailSelectedJobId = "media";
    await loadState();
    state.detailSelectedJobId = "media";
    renderDetail();
    toast("Deleted selected thumbnail.");
    return;
  }
  if (state.detailSelectedSourceUrl || displayItem?.type === "source") {
    toastError("Original source thumbnails are kept.");
    return;
  }
  const selectedMediaId = displayItem?.id && galleryItemById(displayItem.id) ? displayItem.id : item?.id;
  const target = galleryItemById(selectedMediaId);
  if (!target) {
    toastError("Select a Library thumbnail to delete.");
    return;
  }
  if (isImagineRemoteItem(target)) {
    toastError("Imagine originals are not deleted here.");
    return;
  }
  const relatedRemaining = groupItemsFor(target)
    .filter((candidate) => candidate.id !== target.id && ["image", "video"].includes(candidate.type))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  const allRemaining = [...workspaceItems(), ...uploadImageItems()]
    .filter((candidate) => (
      candidate.id !== target.id
        && ["image", "video"].includes(candidate.type)
        && candidate.local_url
    ))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  const remaining = Array.from(
    new Map([...relatedRemaining, ...allRemaining].map((candidate) => [candidate.id, candidate])).values(),
  );
  const ok = await openGalleryActionDialog({
    title: "Delete item",
    message: "Delete this local item?",
    confirmLabel: "Delete",
  });
  if (!ok) return;
  if (target.source === "upload-card") {
    const upload = state.uploads.find((candidate) => candidate.id === target.uploadId);
    if (upload) await deleteUploadedImage(upload);
  } else {
    await api("/api/items/delete", {
      method: "POST",
      body: JSON.stringify({ ids: [target.id] }),
    });
  }
  if (remaining.length) {
    const next = remaining[0];
    state.detailItemId = next.id;
    state.detailSelectedSourceUrl = "";
    state.detailSelectedJobId = "media";
    clearDetailExtendState();
    els.promptInput.value = next.prompt || "";
    autoSizePromptInput();
    syncComposerToDetailItem(next);
    replaceDetailHistory(next.id);
  } else {
    closeDetail();
  }
  toast("Deleted local item.");
  await loadState();
}

function videoIcon(name) {
  const icons = {
    play: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>`,
    pause: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>`,
    muted: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path class="video-mute-slash" d="M6.131 5.331 17.962 17.162" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
    volume: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9H4zm12.5-1.5-1.4 1.4A4.4 4.4 0 0 1 16 12c0 1.2-.3 2.3-.9 3.1l1.4 1.4A6.6 6.6 0 0 0 18 12c0-1.7-.5-3.2-1.5-4.5zM19.3 4.7 17.9 6.1A8.5 8.5 0 0 1 20 12c0 2.2-.8 4.3-2.1 5.9l1.4 1.4A10.5 10.5 0 0 0 22 12c0-2.8-1-5.4-2.7-7.3z"/></svg>`,
  };
  return `<span class="video-icon">${icons[name] || ""}</span>`;
}

function setVideoButtonIcon(button, icon, label) {
  if (!button) return;
  button.innerHTML = videoIcon(icon);
  button.title = label;
  button.setAttribute("aria-label", label);
}

function videoPlayerHtml(src, title = "Video", options = {}) {
  const compact = options.compact === false ? "" : " compact-video-player";
  const extraClass = options.extraClass ? ` ${options.extraClass}` : "";
  const videoClass = options.videoClass ? ` ${options.videoClass}` : "";
  const poster = options.poster ? ` poster="${escapeHtml(options.poster)}"` : "";
  return `<div class="video-player${compact}${extraClass}" data-video-player tabindex="0">
    <video class="custom-video${videoClass}" src="${escapeHtml(src)}" playsinline preload="metadata"${poster}></video>
    <div class="video-controls" data-video-controls>
      <button class="video-play" type="button" aria-label="Play">${videoIcon("play")}</button>
      <span class="video-time"><span data-current>0:00</span><span data-time-separator> / </span><span data-duration>0:00</span></span>
      <input class="video-seek" data-seek type="range" min="0" max="1000" value="0" step="1" aria-label="Seek" />
      <div class="video-seek-ticks" data-seek-ticks aria-hidden="true"></div>
      <button class="video-mute" type="button" aria-label="Mute">${videoIcon("muted")}</button>
      <label class="video-volume">
        <span data-volume-label>100</span>
        <input class="video-volume-slider" data-volume type="range" min="0" max="100" value="100" step="1" aria-label="Volume" />
      </label>
      <button class="video-a" type="button">A</button>
      <button class="video-b" type="button">B</button>
      <select class="video-rate" aria-label="Playback speed">
        <option value="2">2x</option>
        <option value="1.5">1.5x</option>
        <option value="1.25">1.25x</option>
        <option value="1" selected>1x</option>
        <option value="0.75">0.75x</option>
        <option value="0.5">0.5x</option>
        <option value="0.25">0.25x</option>
      </select>
    </div>
  </div>`;
}

function openStudioFullscreen(src, title = "Video") {
  if (!src) return;
  bindCustomVideoPlayers();
  const player = els.studioFullscreenPlayer;
  if (!player?.openStudioVideo) {
    toastError("Studio fullscreen player is not ready.");
    return;
  }
  player.openStudioVideo(src, title);
}

function bindCustomVideoPlayers() {
  $$("[data-video-player]").forEach((player) => {
    if (player.dataset.bound === "1") return;
    player.dataset.bound = "1";
    const video = player.querySelector(".custom-video");
    const playButton = player.querySelector(".video-play");
    const muteButton = player.querySelector(".video-mute");
    const loopButton = player.querySelector(".video-loop");
    const aButton = player.querySelector(".video-a");
    const bButton = player.querySelector(".video-b");
    const fullscreenButton = player.querySelector(".video-fullscreen");
    const rateInput = player.querySelector(".video-rate");
    const volumeInput = player.querySelector("[data-volume]");
    const volumeLabel = player.querySelector("[data-volume-label]");
    const seekInput = player.querySelector("[data-seek]");
    const currentLabel = player.querySelector("[data-current]");
    const separatorLabel = player.querySelector("[data-time-separator]");
    const durationLabel = player.querySelector("[data-duration]");
    const timeLabel = player.querySelector(".video-time");
    const seekTicks = player.querySelector("[data-seek-ticks]");
    const points = { a: null, b: null, hideTimer: null, volumeTimer: null };
    const isDetailPlayer = player.classList.contains("detail-video-player");
    const isExpanded = () => document.fullscreenElement === player || player.classList.contains("studio-visible");
    const isCurrentDetailPlayer = () => (
      isDetailPlayer
      && state.view === "detail"
      && player.isConnected
      && player === els.detailScreen?.querySelector(".detail-video-player")
    );
    const isActive = () => player.isConnected && !player.hidden && (isCurrentDetailPlayer() || isExpanded());
    let seekTickKey = "";

    const renderSeekTicks = (duration) => {
      if (!seekTicks || !isDetailPlayer) return;
      if (!Number.isFinite(duration) || duration <= 0) {
        seekTickKey = "";
        seekTicks.innerHTML = "";
        return;
      }
      const safeDuration = Math.max(0.1, duration);
      const wholeSeconds = Math.floor(safeDuration);
      const fractionalTail = safeDuration - wholeSeconds;
      const ticks = [];
      for (let second = 0; second <= wholeSeconds; second += 1) {
        if (second === wholeSeconds && fractionalTail > 0.05 && fractionalTail < 0.75) continue;
        ticks.push(second);
      }
      if (fractionalTail > 0.05) ticks.push(safeDuration);
      const unique = [];
      ticks.forEach((tick) => {
        const pct = Math.max(0, Math.min(100, (tick / safeDuration) * 100));
        if (unique.some((candidate) => Math.abs(candidate - pct) < 0.35)) return;
        unique.push(pct);
      });
      const visibleTicks = unique.filter((tick) => tick <= 0.01 || tick < 96 || Math.abs(tick - 100) < 0.01);
      if (!visibleTicks.length || Math.abs(visibleTicks[visibleTicks.length - 1] - 100) > 0.01) visibleTicks.push(100);
      const nextKey = `${safeDuration.toFixed(2)}:${visibleTicks.map((tick) => tick.toFixed(3)).join(",")}`;
      if (nextKey === seekTickKey) return;
      seekTickKey = nextKey;
      seekTicks.innerHTML = visibleTicks.map((tick) => `<span style="left:${tick.toFixed(4)}%"></span>`).join("");
    };

    const syncDetailPlayerAspect = () => {
      if (!isDetailPlayer || !video.videoWidth || !video.videoHeight) return;
      const aspect = `${video.videoWidth} / ${video.videoHeight}`;
      player.style.setProperty("--detail-media-aspect", aspect);
      player.closest(".detail-media-shell")?.style.setProperty("--detail-media-aspect", aspect);
    };

    video.preservesPitch = true;
    video.webkitPreservesPitch = true;
    video.mozPreservesPitch = true;
    if (isDetailPlayer) {
      video.loop = true;
      video.muted = false;
      video.removeAttribute("title");
      player.classList.add("controls-hidden");
    }

    const showControls = () => {
      player.classList.remove("controls-hidden");
      window.clearTimeout(points.hideTimer);
      if ((isExpanded() || isDetailPlayer) && !video.paused) {
        points.hideTimer = window.setTimeout(() => {
          player.classList.add("controls-hidden");
        }, 2700);
      }
    };

    const showVolume = () => {
      if (!isDetailPlayer) return;
      player.classList.add("volume-visible");
      window.clearTimeout(points.volumeTimer);
      points.volumeTimer = window.setTimeout(() => {
        player.classList.remove("volume-visible");
      }, 1800);
    };

    const sync = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : 0;
      const current = Number.isFinite(video.currentTime) ? video.currentTime : 0;
      const hasAbPoint = points.a !== null || points.b !== null;
      renderSeekTicks(duration);
      if (hasAbPoint) {
        currentLabel.textContent = `A ${points.a === null ? "--" : formatTime(points.a)} - B ${points.b === null ? "--" : formatTime(points.b)}`;
        if (separatorLabel) {
          separatorLabel.hidden = true;
          separatorLabel.textContent = "";
        }
        durationLabel.hidden = true;
        durationLabel.textContent = "";
        timeLabel?.classList.remove("is-extend-time");
        timeLabel?.classList.add("is-ab-time");
      } else if (isDetailPlayer && state.detailExtend) {
        currentLabel.textContent = formatExtendRange(state.detailExtendStart, selectedExtendDuration(10));
        if (separatorLabel) {
          separatorLabel.hidden = true;
          separatorLabel.textContent = "";
        }
        durationLabel.hidden = true;
        durationLabel.textContent = "";
        timeLabel?.classList.remove("is-ab-time");
        timeLabel?.classList.add("is-extend-time");
      } else {
        currentLabel.textContent = formatTime(current);
        if (separatorLabel) {
          separatorLabel.hidden = false;
          separatorLabel.textContent = " / ";
        }
        durationLabel.hidden = false;
        durationLabel.textContent = formatTime(duration);
        timeLabel?.classList.remove("is-ab-time");
        timeLabel?.classList.remove("is-extend-time");
      }
      seekInput.value = duration ? String(Math.round((current / duration) * 1000)) : "0";
      seekInput.style.setProperty("--range-progress", `${duration ? Math.min(100, Math.max(0, (current / duration) * 100)) : 0}%`);
      setVideoButtonIcon(playButton, video.paused ? "play" : "pause", video.paused ? "Play" : "Pause");
      setVideoButtonIcon(muteButton, video.muted ? "muted" : "volume", video.muted ? "Unmute" : "Mute");
      if (isDetailPlayer) {
        playButton?.removeAttribute("title");
        muteButton?.removeAttribute("title");
      }
      const volumePercent = Math.round((video.volume || 0) * 100);
      if (volumeInput) volumeInput.value = String(volumePercent);
      volumeInput?.style.setProperty("--range-progress", `${volumePercent}%`);
      if (volumeLabel) volumeLabel.textContent = String(volumePercent);
      if (points.a !== null && points.b !== null && current >= points.b) {
        video.currentTime = points.a;
        if (!video.paused) video.play().catch(() => {});
      }
    };

    const updateAb = () => {
      aButton.classList.toggle("active", points.a !== null);
      bButton.classList.toggle("active", points.b !== null);
      sync();
    };

    const resetPlayer = () => {
      points.a = null;
      points.b = null;
      window.clearTimeout(points.hideTimer);
      video.pause();
      video.loop = isDetailPlayer;
      video.playbackRate = 1;
      video.volume = 1;
      video.muted = false;
      video.removeAttribute("title");
      if (rateInput) rateInput.value = "1";
      loopButton?.classList.remove("active");
      player.classList.toggle("controls-hidden", isDetailPlayer);
      updateAb();
      sync();
    };

    const changeVolume = (delta) => {
      const next = Math.max(0, Math.min(1, video.volume + delta));
      video.volume = Number(next.toFixed(2));
      video.muted = video.volume === 0;
      sync();
      showVolume();
      showControls();
    };

    player.openStudioVideo = (src, title = "Video") => {
      resetPlayer();
      video.src = src;
      video.removeAttribute("title");
      player.hidden = false;
      player.classList.add("studio-visible");
      player.requestFullscreen?.()
        .then(() => {
          fullscreenButton?.blur();
          player.focus({ preventScroll: true });
          video.play().catch(() => {});
          showControls();
        })
        .catch((error) => {
          toastError(error.message);
          player.hidden = true;
          player.classList.remove("studio-visible");
          video.removeAttribute("src");
          video.load();
        });
    };

    playButton?.addEventListener("click", () => {
      if (video.paused) video.play().catch((error) => toastError(error.message));
      else video.pause();
      showControls();
    });
    video.addEventListener("click", () => {
      if (isDetailPlayer) {
        if (document.fullscreenElement === player) {
          document.exitFullscreen?.();
          return;
        }
        player.requestFullscreen?.()
          .then(() => {
            player.focus({ preventScroll: true });
            if (video.paused) video.play().catch(() => {});
            showControls();
          })
          .catch((error) => toastError(error.message));
        return;
      }
      if (video.paused) video.play().catch((error) => toastError(error.message));
      else video.pause();
      showControls();
    });
    muteButton?.addEventListener("click", () => {
      video.muted = !video.muted;
      sync();
      showControls();
    });
    volumeInput?.addEventListener("input", () => {
      const next = Math.max(0, Math.min(100, Number(volumeInput.value || 0)));
      video.volume = next / 100;
      video.muted = next === 0;
      sync();
      showVolume();
      showControls();
    });
    loopButton?.addEventListener("click", () => {
      video.loop = !video.loop;
      loopButton.classList.toggle("active", video.loop);
      showControls();
    });
    aButton?.addEventListener("click", () => {
      if (points.a !== null) {
        points.a = null;
      } else {
        points.a = video.currentTime || 0;
        if (points.b !== null && points.b <= points.a) points.b = null;
      }
      updateAb();
      showControls();
    });
    bButton?.addEventListener("click", () => {
      if (points.b !== null) {
        points.b = null;
      } else {
        const current = video.currentTime || 0;
        points.b = points.a !== null ? Math.max(current, points.a + 0.1) : current;
      }
      updateAb();
      showControls();
    });
    rateInput?.addEventListener("change", () => {
      video.playbackRate = Number(rateInput.value || 1);
      video.preservesPitch = true;
      video.webkitPreservesPitch = true;
      video.mozPreservesPitch = true;
      showControls();
    });
    seekInput?.addEventListener("input", () => {
      if (Number.isFinite(video.duration) && video.duration > 0) {
        video.currentTime = (Number(seekInput.value) / 1000) * video.duration;
        if (isCurrentDetailPlayer() && state.detailExtend) {
          state.detailExtendStart = currentDetailVideoTrimStart();
          refreshDetailExtendTimeLabel();
        }
      }
      showControls();
    });
    fullscreenButton?.addEventListener("click", () => {
      fullscreenButton.blur();
      if (document.fullscreenElement === player) {
        document.exitFullscreen?.();
      } else {
        player.requestFullscreen?.()
          .then(() => {
            player.focus({ preventScroll: true });
            showControls();
          })
          .catch((error) => toastError(error.message));
      }
      showControls();
    });
    document.addEventListener("keydown", (event) => {
      if (!isActive()) return;
      const target = event.target;
      if (target instanceof HTMLElement) {
        const tagName = target.tagName;
        if (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(tagName)) return;
      }
      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault();
        event.stopPropagation();
        changeVolume(event.key === "ArrowUp" ? 0.05 : -0.05);
        return;
      }
      const key = event.code === "Space" ? "space" : String(event.key || "").toLowerCase();
      const shortcutMap = {
        space: playButton,
        m: muteButton,
        a: aButton,
        b: bButton,
      };
      const button = shortcutMap[key];
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      button.click();
      showControls();
    });
    player.addEventListener("wheel", (event) => {
      if (!isActive()) return;
      event.preventDefault();
      changeVolume(event.deltaY < 0 ? 0.05 : -0.05);
    }, { passive: false });
    player.addEventListener("mousemove", showControls);
    player.addEventListener("touchstart", showControls, { passive: true });
    document.addEventListener("fullscreenchange", () => {
      const active = document.fullscreenElement === player;
      player.classList.toggle("is-fullscreen", active);
      if (!active && player.id === "studioFullscreenPlayer" && !player.hidden) {
        video.pause();
        video.removeAttribute("src");
        video.load();
        player.hidden = true;
        player.classList.remove("studio-visible", "controls-hidden");
      } else if (!active && isDetailPlayer && !video.paused) {
        player.classList.add("controls-hidden");
      } else if (!active) {
        player.classList.remove("controls-hidden");
      }
      sync();
      if (active || !isDetailPlayer || video.paused) showControls();
    });
    video.addEventListener("loadedmetadata", () => {
      syncDetailPlayerAspect();
      sync();
    });
    video.addEventListener("timeupdate", sync);
    video.addEventListener("play", () => {
      if (isDetailPlayer) {
        window.clearTimeout(points.hideTimer);
        player.classList.add("controls-hidden");
      } else {
        showControls();
      }
    });
    video.addEventListener("pause", showControls);
    sync();
    syncDetailPlayerAspect();
    updateAb();
  });
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = String(total % 60).padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function formatExtendRange(start, duration) {
  const safeStart = Number.isFinite(start) && start > 0 ? start : 0;
  const safeDuration = Number.isFinite(duration) ? duration : selectedExtendDuration(10);
  return `${formatTime(safeStart)} → ${formatTime(safeStart + safeDuration)}`;
}

function detailVideoElement() {
  return els.detailScreen?.querySelector(".detail-video-player .custom-video") || null;
}

function currentDetailVideoTrimStart() {
  const video = detailVideoElement();
  if (!video) return 0;
  const current = Number(video.currentTime);
  const duration = Number(video.duration);
  if (!Number.isFinite(current) || current < 0) return 0;
  if (Number.isFinite(duration) && current >= duration - 0.25) return Math.max(0, duration - 0.25);
  return Number(current.toFixed(3));
}

function clearDetailExtendState() {
  state.detailExtend = false;
  state.detailExtendStart = 0;
  state.detailExtendComposerGuardUntil = 0;
  state.detailExtendComposerGestureActive = false;
  els.detailScreen?.classList.remove("detail-extend-active");
  refreshDetailExtendTimeLabel();
}

function cancelDetailExtend() {
  if (!state.detailExtend) return;
  clearDetailExtendState();
  if (state.mode === "extend") {
    setMode("video", { skipDetailStart: true, skipDetailExtend: true, forceDetailExtendCancel: true });
  }
}

function handleDetailExtendBlankClick(event) {
  if (!state.detailExtend || state.view !== "detail") return;
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (hasDetailExtendComposerIntent()) return;
  if (target.closest(".lab-composer, .detail-prompt-pill")) return;
  if (!target.closest("#detailScreen") && !target.closest(".workspace.show-detail")) return;
  const protectedSelectors = [".detail-media-wrap", ".detail-stack", ".detail-actions"];
  const withinProtectedArea = protectedSelectors.some((selector) => {
    const node = els.detailScreen?.querySelector(selector);
    if (!node) return false;
    const rect = node.getBoundingClientRect();
    return event.clientX >= rect.left
      && event.clientX <= rect.right
      && event.clientY >= rect.top
      && event.clientY <= rect.bottom;
  });
  if (withinProtectedArea) return;
  cancelDetailExtend();
}

function refreshDetailExtendTimeLabel() {
  const player = els.detailScreen?.querySelector(".detail-video-player");
  const video = player?.querySelector(".custom-video");
  const currentLabel = player?.querySelector("[data-current]");
  const separator = player?.querySelector("[data-time-separator]");
  const durationLabel = player?.querySelector("[data-duration]");
  const time = player?.querySelector(".video-time");
  if (!player || !currentLabel || !durationLabel) return;
  if (state.detailExtend) {
    currentLabel.textContent = formatExtendRange(state.detailExtendStart, selectedExtendDuration(10));
    if (separator) {
      separator.hidden = true;
      separator.textContent = "";
    }
    durationLabel.hidden = true;
    durationLabel.textContent = "";
    time?.classList.add("is-extend-time");
    return;
  }
  const current = Number(video?.currentTime);
  const duration = Number(video?.duration);
  currentLabel.textContent = formatTime(Number.isFinite(current) ? current : 0);
  if (separator) {
    separator.hidden = false;
    separator.textContent = " / ";
  }
  durationLabel.hidden = false;
  durationLabel.textContent = formatTime(Number.isFinite(duration) ? duration : 0);
  time?.classList.remove("is-extend-time");
}

function markDetailExtendComposerIntent() {
  if (state.view !== "detail" || !state.detailExtend) return;
  state.detailExtendComposerGuardUntil = Date.now() + 700;
}

function beginDetailExtendComposerGesture() {
  if (state.view !== "detail" || !state.detailExtend) return;
  state.detailExtendComposerGestureActive = true;
  state.detailExtendComposerGuardUntil = Date.now() + 15000;
}

function endDetailExtendComposerGesture() {
  if (!state.detailExtendComposerGestureActive) return;
  state.detailExtendComposerGestureActive = false;
  state.detailExtendComposerGuardUntil = Date.now() + 900;
}

function hasDetailExtendComposerIntent() {
  return Number(state.detailExtendComposerGuardUntil || 0) > Date.now();
}

function ensureDetailExtendComposerState() {
  if (state.view !== "detail" || !state.detailExtend) return;
  if (state.mode !== "extend") {
    setMode("extend", { skipDetailStart: true, skipDetailExtend: true });
    return;
  }
  refreshDetailExtendTimeLabel();
}

function prepareDetailExtendFromCurrentFrame() {
  const item = detailItem();
  const displayItem = detailDisplayItem(item);
  if (state.view !== "detail" || !displayItem || displayItem.type !== "video" || !displayItem.local_url) {
    return false;
  }
  const video = detailVideoElement();
  if (video) video.pause();
  state.detailExtend = true;
  state.detailExtendStart = currentDetailVideoTrimStart();
  setSourceVideoFromLibrary(displayItem, { skipMode: true, silent: true });
  els.detailScreen?.classList.add("detail-extend-active");
  refreshDetailExtendTimeLabel();
  return true;
}

function setMode(mode, options = {}) {
  const promptFocused = document.activeElement === els.promptInput || els.promptInput?.matches(":focus");
  const composerIntent = hasDetailExtendComposerIntent();
  if (mode !== "extend" && state.detailExtend && (!options.userSelect || promptFocused || composerIntent) && !options.forceDetailExtendCancel) {
    mode = "extend";
    options = { ...options, skipDetailStart: true, skipDetailExtend: true };
  }
  const previousMode = state.mode;
  if (mode !== "extend" && state.detailExtend) {
    clearDetailExtendState();
  }
  state.mode = mode;
  if (mode === "extend" && previousMode !== "extend") {
    setVideoModel(state.videoModel);
  }
  const composer = els.promptInput?.closest(".lab-composer");
  composer?.classList.toggle("extend-mode", mode === "extend");
  if (mode === "extend") {
    state.attachmentTrayOpen = false;
  }
  $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.mode === mode));
  $$(".mode-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === mode));

  setControlVisible($("#countControl"), mode === "image");
  setControlVisible($("#durationControl"), mode === "video" || mode === "extend");
  setControlVisible($("#trimQualityControl"), false);
  configureDuration(mode);
  setControlVisible($("#ratioControl"), mode === "image" || mode === "video");
  setControlVisible($("#imageModelControl"), mode === "image");
  setControlVisible($("#resolutionControl"), mode === "image" || mode === "video");
  setControlVisible($("#modelControl"), mode === "video" || mode === "extend");
  setControlVisible($("#analyzeModelControl"), mode === "analyze");
  configureResolution(mode);
  refreshCustomSelects();
  els.submitBtn.textContent = "↑";
  els.submitBtn.setAttribute("aria-label", mode === "analyze" ? "Analyze" : "Generate");
  els.promptInput.placeholder = mode === "analyze"
    ? "Select or attach an image to analyze..."
    : "Describe the scene, motion, edit, or continuation...";
  if (!options.skipDetailStart) {
    syncDetailImageStartForMode(mode);
  }
  renderCategories();
  renderAttachmentTray();
  if (mode === "extend" && !options.skipDetailExtend) {
    prepareDetailExtendFromCurrentFrame();
  } else {
    refreshDetailExtendTimeLabel();
  }
}

function syncDetailImageStartForMode(mode) {
  const item = detailItem();
  if (state.view !== "detail" || !item) {
    if (mode !== "video" && state.startImage?.source === "detail-auto") {
      clearStartImage();
    }
    return;
  }
  const image = selectedDetailImage(item);
  if (mode === "video") {
    if (image) setStartImageFromDetailItem(image);
    else if (state.startImage?.source === "detail-auto") clearStartImage();
    clearDetailAutoEditImages();
    return;
  }
  if (mode === "image") {
    if (image) {
      setEditImageFromDetailItem(image);
      setStartImageFromDetailItem(image);
    }
    else clearDetailAutoEditImages();
    return;
  }
  if (mode !== "video" && state.startImage?.source === "detail-auto") {
    clearStartImage();
  }
  if (mode !== "image") {
    clearDetailAutoEditImages();
  }
}

function setControlVisible(control, visible) {
  if (!control) return;
  control.style.display = visible ? "inline-flex" : "none";
  const custom = control.querySelector(".custom-select");
  if (custom) custom.hidden = !visible;
}

function configureDuration(mode) {
  if (!["video", "extend"].includes(mode)) return;
  const config = mode === "extend"
    ? { min: 2, max: 10, defaultValue: 10 }
    : { min: 1, max: 15, defaultValue: 15 };
  const previous = Number(els.durationInput.value);
  const keepPrevious = state.durationMode === mode
    && Number.isFinite(previous)
    && previous >= config.min
    && previous <= config.max;
  els.durationInput.innerHTML = "";
  for (let value = config.max; value >= config.min; value -= 1) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    els.durationInput.append(option);
  }
  els.durationInput.value = String(keepPrevious ? previous : config.defaultValue);
  state.durationMode = mode;
  syncCustomSelect(els.durationInput);
}

function configureResolution(mode) {
  if (!["image", "video"].includes(mode)) return;
  const options = mode === "image"
    ? [
        { value: "2k", label: "2K" },
        { value: "1k", label: "1K" },
      ]
    : [
        { value: "720p", label: "720P" },
        { value: "480p", label: "480P" },
      ];
  const previous = els.resolutionInput.value;
  const keepPrevious = state.resolutionMode === mode && options.some((option) => option.value === previous);
  els.resolutionInput.innerHTML = "";
  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    els.resolutionInput.append(option);
  });
  els.resolutionInput.value = keepPrevious ? previous : options[0].value;
  state.resolutionMode = mode;
  syncCustomSelect(els.resolutionInput);
}

function initCustomSelects() {
  if (initCustomSelects.done) return;
  initCustomSelects.done = true;
  const selects = [
    els.countInput,
    els.durationInput,
    els.trimQualityInput,
    els.aspectInput,
    els.imageModelInput,
    els.resolutionInput,
    els.videoModelInput,
    els.analyzeModelInput,
  ].filter(Boolean);
  selects.forEach((select) => {
    if (select.dataset.customized === "1") return;
    select.dataset.customized = "1";
    select.classList.add("native-select-hidden");
    const wrapper = document.createElement("div");
    wrapper.className = "custom-select";
    wrapper.dataset.selectId = select.id;
    const button = document.createElement("button");
    button.className = "custom-select-button";
    button.type = "button";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const menu = document.createElement("div");
    menu.className = "custom-select-menu";
    menu.setAttribute("role", "listbox");
    wrapper.append(button, menu);
    select.insertAdjacentElement("afterend", wrapper);
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleCustomSelect(wrapper);
    });
    select.addEventListener("change", () => syncCustomSelect(select));
    syncCustomSelect(select);
  });

  document.addEventListener("click", closeCustomSelects);
  document.addEventListener("click", closeAccountTierMenusOnOutsideClick);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCustomSelects();
  });
}

function refreshCustomSelects() {
  [els.countInput, els.durationInput, els.trimQualityInput, els.aspectInput, els.imageModelInput, els.resolutionInput, els.videoModelInput, els.analyzeModelInput]
    .filter(Boolean)
    .forEach(syncCustomSelect);
}

function customSelectWrapper(select) {
  if (!select) return null;
  return select.parentElement?.querySelector(`.custom-select[data-select-id="${select.id}"]`) || null;
}

function syncCustomSelect(select) {
  const wrapper = customSelectWrapper(select);
  if (!wrapper) return;
  const button = wrapper.querySelector(".custom-select-button");
  const menu = wrapper.querySelector(".custom-select-menu");
  const selected = select.selectedOptions?.[0] || select.options?.[0];
  if (!button || !menu) return;
  button.textContent = selected?.textContent || "";
  menu.innerHTML = Array.from(select.options).map((option) => {
    const isActive = option.value === select.value;
    const activeClass = isActive ? " active" : "";
    return `<button class="custom-select-option${activeClass}" type="button" role="option" aria-selected="${isActive ? "true" : "false"}" data-value="${escapeHtml(option.value)}">${escapeHtml(option.textContent)}</button>`;
  }).join("");
  menu.querySelectorAll(".custom-select-option").forEach((optionButton) => {
    optionButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      select.value = optionButton.dataset.value || "";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      closeCustomSelects();
    });
  });
}

function toggleCustomSelect(wrapper) {
  const open = !wrapper.classList.contains("open");
  closeCustomSelects();
  if (!open) return;
  wrapper.classList.add("open");
  wrapper.querySelector(".custom-select-button")?.setAttribute("aria-expanded", "true");
}

function closeCustomSelects() {
  $$(".custom-select.open").forEach((wrapper) => {
    wrapper.classList.remove("open");
    wrapper.querySelector(".custom-select-button")?.setAttribute("aria-expanded", "false");
  });
}

function updateSidebarTogglePosition() {
  const upperRect = (els.galleryNavBtn || els.imagineNavBtn)?.getBoundingClientRect();
  const searchRect = els.sidebarSearchLabel?.getBoundingClientRect();
  if (!upperRect?.height || !searchRect?.height) return;
  const midpoint = upperRect.bottom + ((searchRect.top - upperRect.bottom) / 2);
  document.documentElement.style.setProperty("--sidebar-toggle-top", `${midpoint}px`);
}

function setSidebarCollapsed(collapsed) {
  state.sidebarCollapsed = collapsed;
  localStorage.setItem("grokStudioSidebarCollapsed", collapsed ? "1" : "0");
  els.appShell.classList.toggle("sidebar-collapsed", collapsed);
  els.sidebarOpenBtn.hidden = true;
  els.sidebarCloseBtn.textContent = collapsed ? ">>" : "<<";
  els.sidebarCloseBtn.dataset.symbol = collapsed ? ">>" : "<<";
  els.sidebarCloseBtn.removeAttribute("title");
  els.sidebarCloseBtn.setAttribute("aria-label", collapsed ? "Open sidebar" : "Hide sidebar");
  updateSidebarTogglePosition();
  window.requestAnimationFrame(updateSidebarTogglePosition);
}

function updateSelectionControls() {
  const count = state.selectedItems.size;
  const selectedLibraryItems = state.items.filter((item) => state.selectedItems.has(item.id));
  const canMoveToGallery = !state.workspaceFolderId
    && count > 0
    && selectedLibraryItems.length === count
    && selectedLibraryItems.every((item) => !itemGalleryFolderId(item));
  if (els.selectionBar) els.selectionBar.hidden = true;
  if (els.selectionCount) els.selectionCount.textContent = `Selected: ${count}`;
  els.libraryActions?.classList.toggle("selection-active", count > 0);
  if (els.refreshBtn) {
    els.refreshBtn.textContent = count > 0 ? `Selected: ${count}` : "Refresh";
    els.refreshBtn.disabled = count > 0;
  }
  els.downloadSelectedBtn.disabled = false;
  els.deleteSelectedBtn.disabled = false;
  els.deleteSelectedBtn.textContent = "Delete";
  if (els.moveToGalleryBtn) els.moveToGalleryBtn.hidden = !canMoveToGallery;
  if (els.librarySelectionClearBtn) els.librarySelectionClearBtn.hidden = count === 0;
}

function selectedDownloadableItems() {
  const items = [];
  Array.from(state.selectedItems).forEach((id) => {
    items.push(...relatedDownloadItemsFor(galleryItemById(id)));
  });
  return uniqueDownloadItems(items);
}

function downloadSelectedItems() {
  const items = selectedDownloadableItems();
  if (!items.length) {
    toastError("Select local media to download.");
    return;
  }
  downloadItems(items);
}

function downloadName(item) {
  const urlName = decodeURIComponent(String(item.local_url || "").split("/").pop()?.split("?")[0] || "");
  return urlName || item.title || "grok-media";
}

async function openMediaFolder() {
  await api("/api/open-media-folder", { method: "POST", body: "{}" });
  toast("Opening media folder.");
}

async function setLibraryFolder() {
  const current = state.library?.external
    ? state.library.root
    : defaultLibraryFolderPromptPath();
  const data = await api("/api/choose-library-folder", {
    method: "POST",
    body: JSON.stringify({ current }),
  });
  if (data.cancelled) return;
  window.location.reload();
}

function defaultLibraryFolderPromptPath() {
  return state.library?.default_folder_path || "";
}

function closeLibraryFolderDialog() {
  state.libraryFolderOverlay?.remove();
  state.libraryFolderOverlay = null;
}

function closeMoveToGalleryDialog() {
  state.moveToGalleryOverlay?.remove();
  state.moveToGalleryOverlay = null;
}

function openMoveToGalleryDialog(itemIds = null, options = {}) {
  closeMoveToGalleryDialog();
  const moveIds = Array.isArray(itemIds) && itemIds.length
    ? itemIds.map(String)
    : Array.from(state.selectedItems);
  if (!moveIds.length) return;
  let selectedPrimaryId = primaryGalleryFolders().some((folder) => folder.id === state.selectedPrimaryFolderId)
    ? state.selectedPrimaryFolderId
    : (primaryGalleryFolders()[0]?.id || "");
  let selectedSecondaryId = "";
  const overlay = document.createElement("div");
  overlay.className = "move-gallery-overlay";
  overlay.innerHTML = `
    <section class="move-gallery-modal" role="dialog" aria-modal="true" aria-label="Move to Gallery">
      <header>
        <div><span>Seleted Items</span><h3>Choose a Gallery Folder</h3></div>
      </header>
      <div class="move-gallery-layout">
        <section class="move-gallery-primary-panel primary-folder-panel" aria-label="Primary folders">
          <div class="folder-panel-heading">
            <button class="collection-heading-button move-gallery-collection" type="button" aria-pressed="false">Collection</button>
          </div>
          <div class="move-gallery-primary-list primary-folder-list"></div>
        </section>
        <section class="move-gallery-secondary-panel secondary-folder-panel" aria-label="Secondary folders">
          <div class="folder-panel-heading move-gallery-secondary-heading">
            <strong class="move-gallery-secondary-title"></strong>
            <div class="move-gallery-actions">
              <button class="make-folder-button move-gallery-make" type="button"><span aria-hidden="true">+</span> Make</button>
              <button class="rename-folder-button move-gallery-rename" type="button"><span aria-hidden="true">=</span> Rename</button>
              <button class="delete-folder-button move-gallery-delete" type="button"><span aria-hidden="true">-</span> Delete</button>
            </div>
          </div>
          <div class="move-gallery-secondary-list secondary-folder-grid"></div>
        </section>
      </div>
    </section>
  `;
  document.body.append(overlay);
  state.moveToGalleryOverlay = overlay;
  const primaryList = overlay.querySelector(".move-gallery-primary-list");
  const secondaryList = overlay.querySelector(".move-gallery-secondary-list");
  const collectionButton = overlay.querySelector(".move-gallery-collection");
  const secondaryTitle = overlay.querySelector(".move-gallery-secondary-title");
  const makeButton = overlay.querySelector(".move-gallery-make");
  const renameButton = overlay.querySelector(".move-gallery-rename");
  const deleteButton = overlay.querySelector(".move-gallery-delete");
  let collectionSelected = !selectedPrimaryId;
  const syncActionState = () => {
    if (collectionButton) {
      collectionButton.classList.toggle("active", collectionSelected);
      collectionButton.setAttribute("aria-pressed", collectionSelected ? "true" : "false");
    }
    if (makeButton) makeButton.disabled = !collectionSelected && !selectedPrimaryId;
    const selectedActionFolderId = collectionSelected ? selectedPrimaryId : selectedSecondaryId;
    if (renameButton) renameButton.disabled = !selectedActionFolderId;
    if (deleteButton) deleteButton.disabled = !selectedActionFolderId;
  };
  const reorderMovePrimaryFolder = async (draggedId, targetId) => {
    if (!draggedId || !targetId || draggedId === targetId) return;
    const folders = primaryGalleryFolders();
    const draggedIndex = folders.findIndex((folder) => folder.id === draggedId);
    const targetIndex = folders.findIndex((folder) => folder.id === targetId);
    if (draggedIndex < 0 || targetIndex < 0) return;
    const [dragged] = folders.splice(draggedIndex, 1);
    folders.splice(targetIndex, 0, dragged);
    await saveGalleryFolderLayout(folders.map((folder, index) => ({ id: folder.id, order: index })));
  };
  const moveSecondaryFolderToSlotInDialog = async (folderId, rawSlot) => {
    const folder = galleryFolderById(folderId);
    if (!folder?.parent_id) return;
    const slot = Math.max(0, Number(rawSlot) || 0);
    const siblings = secondaryGalleryFolders(folder.parent_id);
    const displayedFolder = siblings.find((candidate) => candidate.id === folderId);
    const occupied = siblings.find((candidate) => candidate.id !== folderId && Number(candidate.grid_slot) === slot);
    const oldSlot = Math.max(0, Number(displayedFolder?.grid_slot ?? folder.grid_slot) || 0);
    const entries = [{ id: folderId, grid_slot: slot }];
    if (occupied) entries.push({ id: occupied.id, grid_slot: oldSlot });
    await saveGalleryFolderLayout(entries);
    state.gallerySort = "";
    state.galleryDraftLayout = null;
  };
  const renderSecondary = () => {
    const folders = selectedPrimaryId ? secondaryGalleryFolders(selectedPrimaryId) : [];
    if (!folders.some((folder) => folder.id === selectedSecondaryId)) selectedSecondaryId = "";
    if (secondaryTitle) secondaryTitle.textContent = "";
    const maxSlot = Math.max(11, ...folders.map((folder) => Number(folder.grid_slot) || 0)) + 4;
    const secondarySlots = Array.from({ length: maxSlot + 1 }, (_, slot) => {
      const folder = folders.find((candidate) => Number(candidate.grid_slot) === slot);
      return folder
        ? `<button class="secondary-folder-card${folder.id === selectedSecondaryId ? " active" : ""}" type="button" draggable="true" data-move-secondary-id="${escapeHtml(folder.id)}" data-grid-slot="${slot}">
            ${folderCardIconHtml()}
            <strong>${escapeHtml(folder.name)}</strong>
          </button>`
        : `<button class="secondary-folder-slot" type="button" tabindex="-1" aria-label="Empty folder position" data-grid-slot="${slot}"></button>`;
    });
    secondaryList.innerHTML = folders.length
      ? secondarySlots.join("")
      : `<div class="folder-gallery-empty">${selectedPrimaryId ? "No workspace in this collection." : "Select a collection."}</div>`;
    secondaryList.querySelectorAll("[data-move-secondary-id]").forEach((button) => {
      button.addEventListener("click", () => {
        const nextId = button.dataset.moveSecondaryId || "";
        selectedSecondaryId = selectedSecondaryId === nextId ? "" : nextId;
        collectionSelected = false;
        renderSecondary();
        syncActionState();
      });
      button.addEventListener("dblclick", () => {
        moveSelectedItemsToGallery(button.dataset.moveSecondaryId || "", moveIds, options)
          .catch((error) => toastError(error.message));
      });
      button.addEventListener("dragstart", (event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("application/x-grok-move-secondary-folder", button.dataset.moveSecondaryId || "");
        button.classList.add("dragging");
      });
      button.addEventListener("dragend", () => button.classList.remove("dragging"));
    });
    secondaryList.querySelectorAll("[data-grid-slot]").forEach((slot) => {
      slot.addEventListener("dragover", (event) => {
        if (!event.dataTransfer.types.includes("application/x-grok-move-secondary-folder")) return;
        event.preventDefault();
        slot.classList.add("drop-target");
        event.dataTransfer.dropEffect = "move";
      });
      slot.addEventListener("dragleave", () => slot.classList.remove("drop-target"));
      slot.addEventListener("drop", (event) => {
        event.preventDefault();
        slot.classList.remove("drop-target");
        moveSecondaryFolderToSlotInDialog(
          event.dataTransfer.getData("application/x-grok-move-secondary-folder"),
          slot.dataset.gridSlot,
        )
          .then(() => {
            renderPrimary();
            renderSecondary();
            if (state.view === "folder-gallery") renderFolderGallery();
          })
          .catch((error) => toastError(error.message));
      });
    });
    syncActionState();
    requestAnimationFrame(() => requestAnimationFrame(() => syncFolderGridRows(secondaryList, 9)));
  };
  const renderPrimary = () => {
    const folders = primaryGalleryFolders();
    if (!folders.some((folder) => folder.id === selectedPrimaryId)) selectedPrimaryId = "";
    primaryList.innerHTML = folders.length
      ? folders.map((folder) => `
        <button class="primary-folder-card${folder.id === selectedPrimaryId ? " active" : ""}" type="button" draggable="true" data-move-primary-id="${escapeHtml(folder.id)}">
          ${folderCardIconHtml()}
          <span class="folder-card-copy"><strong>${escapeHtml(folder.name)}</strong></span>
        </button>
      `).join("")
      : `<div class="folder-gallery-empty">No collection yet.</div>`;
    primaryList.querySelectorAll("[data-move-primary-id]").forEach((button) => {
      button.addEventListener("click", () => {
        const nextId = button.dataset.movePrimaryId || "";
        selectedPrimaryId = selectedPrimaryId === nextId ? "" : nextId;
        selectedSecondaryId = "";
        collectionSelected = false;
        renderPrimary();
        renderSecondary();
      });
      button.addEventListener("dragstart", (event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("application/x-grok-move-primary-folder", button.dataset.movePrimaryId || "");
        button.classList.add("dragging");
      });
      button.addEventListener("dragend", () => button.classList.remove("dragging"));
      button.addEventListener("dragover", (event) => {
        if (!event.dataTransfer.types.includes("application/x-grok-move-primary-folder")) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
      });
      button.addEventListener("drop", (event) => {
        event.preventDefault();
        reorderMovePrimaryFolder(
          event.dataTransfer.getData("application/x-grok-move-primary-folder"),
          button.dataset.movePrimaryId || "",
        )
          .then(() => {
            renderPrimary();
            renderSecondary();
            if (state.view === "folder-gallery") renderFolderGallery();
          })
          .catch((error) => toastError(error.message));
      });
    });
    syncActionState();
  };
  collectionButton?.addEventListener("click", () => {
    collectionSelected = true;
    selectedSecondaryId = "";
    renderPrimary();
    renderSecondary();
  });
  makeButton?.addEventListener("click", () => {
    const parentId = collectionSelected ? "" : selectedPrimaryId;
    makeGalleryFolder({ parentId, render: false })
      .then((folder) => {
        if (!folder) return;
        if (folder.parent_id) {
          selectedPrimaryId = folder.parent_id;
          selectedSecondaryId = folder.id;
          collectionSelected = false;
        }
        else {
          selectedPrimaryId = folder.id;
          selectedSecondaryId = "";
          collectionSelected = true;
        }
        renderPrimary();
        renderSecondary();
      })
      .catch((error) => toastError(error.message));
  });
  renameButton?.addEventListener("click", () => {
    renameGalleryFolder(collectionSelected ? selectedPrimaryId : selectedSecondaryId)
      .then((folder) => {
        if (!folder) return;
        renderPrimary();
        renderSecondary();
      })
      .catch((error) => toastError(error.message));
  });
  deleteButton?.addEventListener("click", () => {
    const folderId = collectionSelected ? selectedPrimaryId : selectedSecondaryId;
    const folder = galleryFolderById(folderId);
    deleteGalleryFolder(folderId)
      .then(async (deleted) => {
        if (!deleted || !folder) return;
        if (!collectionSelected) selectedSecondaryId = "";
        else {
          selectedPrimaryId = "";
          selectedSecondaryId = "";
          collectionSelected = true;
        }
        await loadState();
        renderPrimary();
        renderSecondary();
      })
      .catch((error) => toastError(error.message));
  });
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeMoveToGalleryDialog();
  });
  renderPrimary();
  renderSecondary();
}

async function moveSelectedItemsToGallery(folderId, itemIds = null, options = {}) {
  const ids = Array.isArray(itemIds) && itemIds.length ? itemIds : Array.from(state.selectedItems);
  const remoteSelection = imagineRemoteMoveSelectionForIds(ids, { related: !options.singleRemote });
  const remoteItems = remoteSelection.items;
  const remoteIds = new Set(remoteItems.map((item) => item.id));
  const localIds = ids.filter((id) => {
    const item = galleryItemById(id);
    return item && !isImagineRemoteItem(item) && !remoteIds.has(id);
  });
  let movedCount = 0;
  if (localIds.length) {
    const data = await api("/api/items/move-to-gallery", {
      method: "POST",
      body: JSON.stringify({ ids: localIds, folder_id: folderId }),
    });
    movedCount += Number(data.count || localIds.length || 0);
  }
  if (remoteItems.length) {
    const data = await api("/api/imagine/remote/import-to-gallery", {
      method: "POST",
      body: JSON.stringify({
        folder_id: folderId,
        items: remoteItems.map((item) => imagineRemoteMovePayload(
          item,
          remoteSelection.primaryByItemId.get(item.id),
        )),
      }),
    });
    movedCount += Number(data.count || remoteItems.length || 0);
  }
  closeMoveToGalleryDialog();
  state.selectedItems.clear();
  await loadState();
  toast(`Moved ${movedCount || ids.length} item(s) to Gallery.`);
}

function selectedImagineRemoteItemIds() {
  return Array.from(state.selectedItems)
    .filter((id) => isImagineRemoteItem(galleryItemById(id)));
}

function importSelectedImagineItems() {
  const ids = selectedImagineRemoteItemIds();
  if (!ids.length) {
    toastError("Select Imagine item(s) to import.");
    return;
  }
  openMoveToGalleryDialog(ids);
}

function imagineRemoteMoveSelectionForIds(ids, options = {}) {
  const unique = new Map();
  const primaryByItemId = new Map();
  const includeRelated = options.related !== false;
  ids.forEach((id) => {
    const item = galleryItemById(id);
    if (!isImagineRemoteItem(item)) return;
    if (!includeRelated) {
      unique.set(item.id, item);
      primaryByItemId.set(item.id, item);
      return;
    }
    const group = groupItemsFor(item).filter(isImagineRemoteItem);
    const primary = group.find((candidate) => candidate.id === item.id) || representativeMediaItem(group) || item;
    group.forEach((candidate) => {
      if (!candidate?.id) return;
      unique.set(candidate.id, candidate);
      if (primary && !primaryByItemId.has(candidate.id)) {
        primaryByItemId.set(candidate.id, primary);
      }
    });
  });
  return { items: Array.from(unique.values()), primaryByItemId };
}

function imagineRemoteMoveItemsForIds(ids) {
  return imagineRemoteMoveSelectionForIds(ids).items;
}

function imagineRemoteMovePayload(item, primaryItem = null) {
  const primary = primaryItem && isImagineRemoteItem(primaryItem) ? primaryItem : null;
  return {
    id: item.id,
    type: item.type,
    title: item.title || "",
    prompt: item.prompt || "",
    created_at: item.created_at || "",
    local_url: item.local_url || "",
    remote_url: item.remote_url || "",
    mime: item.mime || "",
    request_id: item.request_id || "",
    metadata: item.metadata || {},
    primary_remote_item_id: primary?.id || "",
    primary_remote_url: primary?.remote_url || "",
    primary_local_url: primary?.local_url || "",
    primary_type: primary?.type || "",
    primary_created_at: primary?.created_at || "",
  };
}

function openLibraryFolderDialog(current) {
  closeLibraryFolderDialog();
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "library-folder-overlay";
    overlay.innerHTML = `
      <section class="library-folder-modal" role="dialog" aria-modal="true" aria-label="Library Folder Path">
        <h3>Library Folder Path</h3>
        <input class="library-folder-input" type="text" value="${escapeHtml(current || "")}" autocomplete="off" spellcheck="false" />
        <div class="library-folder-actions">
          <button class="ghost-button library-folder-cancel" type="button">취소</button>
          <button class="primary-button library-folder-confirm" type="button">확인</button>
        </div>
      </section>
    `;
    document.body.append(overlay);
    state.libraryFolderOverlay = overlay;

    const input = overlay.querySelector(".library-folder-input");
    const settle = (value) => {
      closeLibraryFolderDialog();
      resolve(value);
    };
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) settle(null);
    });
    overlay.querySelector(".library-folder-cancel")?.addEventListener("click", () => settle(null));
    overlay.querySelector(".library-folder-confirm")?.addEventListener("click", () => settle(input?.value || ""));
    overlay.querySelector(".library-folder-modal")?.addEventListener("keydown", (event) => {
      if (event.key === "Escape") settle(null);
      if (event.key === "Enter") {
        event.preventDefault();
        settle(input?.value || "");
      }
    });
    window.setTimeout(() => {
      input?.focus();
      input?.select();
    }, 0);
  });
}

async function deleteSelectedItems() {
  if (!state.selectedItems.size) {
    toastError("Select local media to delete.");
    return;
  }
  const selectedCount = state.selectedItems.size;
  const targets = deletionTargetsForIds(Array.from(state.selectedItems));
  const targetCount = deletionTargetCount(targets);
  if (!targetCount) {
    toastError("Select local media to delete.");
    return;
  }
  const relatedCount = Math.max(0, targetCount - selectedCount);
  const message = relatedCount
    ? `Delete ${selectedCount} selected item(s) and ${relatedCount} related item(s)?`
    : `Delete ${targetCount} item(s) and their local files?`;
  const ok = window.confirm(message);
  if (!ok) return;
  await deleteDeletionTargets(targets);
  state.selectedItems.clear();
  toast(`Deleted ${targetCount} local item(s).`);
  await loadState();
}

function deletionTargetsForIds(ids) {
  const targets = emptyDeletionTargets();
  ids.forEach((id) => {
    mergeDeletionTargets(targets, deletionTargetsForItem(galleryItemById(id)));
  });
  return targets;
}

function deletionTargetsForItem(item) {
  const targets = emptyDeletionTargets();
  if (!item?.id) return targets;
  if (isImagineRemoteItem(item)) return targets;
  const relatedItems = ["image", "video"].includes(item.type) ? groupItemsFor(item) : [item];
  const candidates = relatedItems.length ? relatedItems : [item];
  candidates.forEach((candidate) => {
    if (!candidate?.id) return;
    if (candidate.source === "upload-card") {
      const uploadId = candidate.uploadId || String(candidate.id).replace(/^upload-card:/, "");
      if (uploadId) targets.uploadIds.add(uploadId);
      return;
    }
    if (candidate.type === "prompt" || ["image", "video"].includes(candidate.type)) {
      targets.itemIds.add(candidate.id);
    }
  });
  return targets;
}

function emptyDeletionTargets() {
  return { itemIds: new Set(), uploadIds: new Set() };
}

function mergeDeletionTargets(targets, nextTargets) {
  nextTargets?.itemIds?.forEach((id) => targets.itemIds.add(id));
  nextTargets?.uploadIds?.forEach((id) => targets.uploadIds.add(id));
  return targets;
}

function deletionTargetCount(targets) {
  return (targets?.itemIds?.size || 0) + (targets?.uploadIds?.size || 0);
}

async function deleteDeletionTargets(targets) {
  const itemIds = Array.from(targets.itemIds);
  if (itemIds.length) {
    await api("/api/items/delete", {
      method: "POST",
      body: JSON.stringify({ ids: itemIds }),
    });
  }
  for (const uploadId of Array.from(targets.uploadIds)) {
    const upload = state.uploads.find((candidate) => candidate.id === uploadId);
    if (upload) await deleteUploadedImage(upload);
  }
}

async function deleteSingleGalleryItem(item) {
  if (!item?.id) return;
  const targets = deletionTargetsForItem(item);
  const targetCount = deletionTargetCount(targets);
  if (!targetCount) {
    toastError(isImagineRemoteItem(item) ? "Imagine originals are not deleted here." : "Select local media to delete.");
    return;
  }
  const relatedCount = item.type === "prompt" ? 0 : Math.max(0, targetCount - 1);
  const ok = await openGalleryActionDialog({
    title: item.type === "prompt" ? "Delete Prompt" : "Delete item",
    message: item.type === "prompt"
      ? "Delete this prompt?"
      : relatedCount
        ? `Delete this item and ${relatedCount} related item(s)?`
        : "Delete this local item?",
    confirmLabel: "Delete",
  });
  if (!ok) return;
  await deleteDeletionTargets(targets);
  if (state.detailItemId && targets.itemIds.has(state.detailItemId)) closeDetail();
  toast(targetCount > 1 ? `Deleted ${targetCount} local item(s).` : "Deleted local item.");
  await loadState();
}

async function submit() {
  reportClientEvent("submit-click", collectFormStatus());
  const prompt = els.promptInput.value.trim();
  if (!prompt && state.mode !== "analyze") {
    toastError("Write a prompt first.");
    reportClientEvent("submit-blocked", { reason: "missing-prompt" });
    return;
  }

  els.submitBtn.disabled = true;
  closeComposerTransientPanels();
  try {
    if (state.mode === "image") {
      await submitImage(prompt);
    } else if (state.mode === "video") {
      await submitVideo(prompt);
    } else if (state.mode === "extend") {
      await submitExtend(prompt);
    } else {
      await submitAnalyze();
    }
    await loadState();
  } catch (error) {
    reportClientEvent("submit-error", { message: error.message });
    showErrorPanel("Job failed", error.message);
  } finally {
    els.submitBtn.disabled = false;
    setMode(state.mode);
    closeComposerTransientPanels();
  }
}

async function submitAnalyze() {
  const image = analyzeImageSource();
  if (!image) {
    throw new Error("Choose an image in the detail screen or attach an image first.");
  }
  const data = await api("/api/analyze", {
    method: "POST",
    body: JSON.stringify({
      image,
      model: els.analyzeModelInput?.value || "grok-4.3",
    }),
  });
  openPromptEditor(null, {
    create: true,
    mode: "analyze",
    prompt: data.english || "",
    translation: data.korean || "",
  });
  reportClientEvent("analyze-completed", { model: data.model || "" });
}

function analyzeImageSource() {
  if (state.view === "detail") {
    const image = selectedDetailImage(detailItem());
    if (image?.local_url) return image.local_url;
  }
  const attached = state.editImages.find((source) => source?.value);
  if (attached?.value) return attached.value;
  if (state.startImage?.value) return state.startImage.value;
  return "";
}

async function submitImage(prompt) {
  const images = state.editImages.map((source) => source.value).slice(0, 3);
  if (images.length) toast(`Using ${images.length} source image(s)...`);
  const data = await api("/api/image", {
    method: "POST",
    body: JSON.stringify(basePayload(prompt, {
      model: selectedImageModel(),
      n: selectedCount(),
      aspect_ratio: els.aspectInput.value,
      resolution: imageResolution(),
      images,
    })),
  });
  await activateSubmittedDetailJob(data.job);
  reportClientEvent("image-job-started", { jobId: data.job.id });
}

function ensureDetailStartImageForVideo() {
  if (state.view !== "detail") return;
  const source = selectedDetailSource();
  if (source?.local_url) {
    const imageSource = detailSourceAsImageSource(source);
    if (imageSource && state.startImage?.value !== imageSource.value) {
      setStartImageSource(imageSource);
    }
    return;
  }
  const image = selectedDetailImage(detailItem());
  if (image?.type === "image" && image.local_url && state.startImage?.value !== image.local_url) {
    setStartImageFromDetailItem(image);
  }
}

async function submitVideo(prompt) {
  const startFile = els.startImageFile.files?.[0];
  if (!startFile) {
    ensureDetailStartImageForVideo();
  }
  if (state.startImage && state.referenceImages.length) {
    throw new Error("Use either Start image or Reference Image, not both.");
  }
  if (startFile && (!state.startImage || state.startImage.source !== "file")) {
    await setStartImageFromFile(startFile);
  }
  const startImage = state.startImage?.value || "";
  const referenceImages = state.referenceImages.map((source) => source.value).slice(0, 7);
  if (referenceImages.length) toast(`Using ${referenceImages.length} reference image(s)...`);
  const data = await api("/api/video", {
    method: "POST",
    body: JSON.stringify(basePayload(prompt, {
      duration: selectedDuration(15),
      model: selectedVideoModel(),
      aspect_ratio: els.aspectInput.value,
      resolution: videoResolution(),
      image: startImage,
      image_item_id: state.startImage?.itemId || undefined,
      reference_images: referenceImages,
    })),
  });
  await activateSubmittedDetailJob(data.job);
  reportClientEvent("video-job-started", { jobId: data.job.id });
}

async function submitExtend(prompt) {
  const uploadFile = state.sourceVideo?.source === "file"
    ? state.sourceVideo.file
    : els.sourceVideoFile.files?.[0];
  const uploaded = uploadFile ? await readAsDataUrl(uploadFile) : "";
  if (uploadFile) {
    const file = uploadFile;
    toast(`Reading source video: ${file.name} (${formatBytes(file.size)})`);
  }
  const sourceItemId = state.sourceVideo?.source === "library"
    ? state.sourceVideo.id
    : els.sourceVideoSelect.value;
  if (!sourceItemId && !uploaded) {
    throw new Error("Choose a Library Video or upload MP4 first.");
  }
  const sourceTrimEnd = state.detailExtend
    ? Number((state.detailExtendStart || 0).toFixed(3))
    : currentSourceVideoTrimEnd();
  const data = await api("/api/video/extend", {
    method: "POST",
    body: JSON.stringify(basePayload(prompt, {
      duration: selectedExtendDuration(10),
      model: selectedVideoModel(),
      source_item_id: sourceItemId,
      video: uploaded,
      source_trim_end: sourceTrimEnd,
      source_trim_quality: "high",
    })),
  });
  await activateSubmittedDetailJob(data.job);
  reportClientEvent("extend-job-started", { jobId: data.job.id });
}

async function activateSubmittedDetailJob(job) {
  if (state.view !== "detail" || !job?.id) return;
  const previousJobId = state.detailSelectedJobId;
  const previousJob = previousJobId && previousJobId !== "media"
    ? state.jobs.find((candidate) => candidate.id === previousJobId)
    : null;
  if (previousJob?.status === "failed") {
    state.jobs = state.jobs.filter((candidate) => candidate.id !== previousJob.id);
    await api(`/api/jobs/${previousJob.id}/dismiss`, { method: "POST", body: "{}" })
      .catch((error) => console.warn(error));
  }
  state.detailSelectedJobId = job.id;
  if (!state.jobs.some((candidate) => candidate.id === job.id)) {
    state.jobs.unshift(job);
  }
  renderJobs();
  renderDetail();
}

function basePayload(prompt, extras = {}) {
  const detail = detailItem();
  const groupId = detail?.metadata?.group_id || detail?.id || "";
  const preview = detailSubmitPreview();
  return {
    prompt,
    category: els.categoryInput.value || defaultCategory(),
    tags: els.tagsInput.value || "",
    group_id: groupId || undefined,
    parent_id: detail?.id || undefined,
    gallery_folder_id: state.workspaceFolderId || undefined,
    preview_url: preview.url || undefined,
    preview_type: preview.type || undefined,
    ...extras,
  };
}

function composerSubmitPreview() {
  if (state.mode === "image") {
    const image = state.editImages.find((source) => source?.previewUrl);
    if (image?.previewUrl) return { url: image.previewUrl, type: "image" };
  }
  if (state.mode === "video") {
    if (state.startImage?.previewUrl) return { url: state.startImage.previewUrl, type: "image" };
    const reference = state.referenceImages.find((source) => source?.previewUrl);
    if (reference?.previewUrl) return { url: reference.previewUrl, type: "image" };
  }
  if (state.mode === "extend" && state.sourceVideo?.previewUrl) {
    return { url: state.sourceVideo.previewUrl, type: "video" };
  }
  return {};
}

function detailSubmitPreview() {
  const item = detailItem();
  if (state.view !== "detail" || !item) return composerSubmitPreview();
  if (state.mode === "video" && state.startImage?.previewUrl) {
    return { url: state.startImage.previewUrl, type: "image" };
  }
  if (state.mode === "image") {
    const image = selectedDetailImage(item);
    if (image?.local_url) return { url: image.local_url, type: "image" };
  }
  const displayItem = detailDisplayItem(item);
  if (!displayItem?.local_url) return {};
  return { url: displayItem.local_url, type: displayItem.type === "video" ? "video" : "image" };
}

function defaultCategory() {
  if (state.mode === "image") return "Image";
  if (state.mode === "video" || state.mode === "extend") return "Video";
  if (state.mode === "analyze") return "Prompt";
  return "Inbox";
}

function imageResolution() {
  return ["1k", "2k"].includes(els.resolutionInput.value) ? els.resolutionInput.value : "2k";
}

function videoResolution() {
  return ["480p", "720p"].includes(els.resolutionInput.value) ? els.resolutionInput.value : "720p";
}

function selectedImageModel() {
  return ["grok-imagine-image", "grok-imagine-image-quality"].includes(state.imageModel)
    ? state.imageModel
    : "grok-imagine-image";
}

function selectedVideoModel() {
  if ([VIDEO_MODEL_15, VIDEO_MODEL_15_PREVIEW].includes(state.videoModel)) {
    return state.videoModel;
  }
  if (state.videoModel === "") return undefined;
  return VIDEO_MODEL_15;
}

function selectedDuration(fallback) {
  const min = state.mode === "extend" ? 2 : 1;
  const max = state.mode === "extend" ? 10 : 15;
  const value = Number(els.durationInput.value || fallback);
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, Math.min(max, Math.round(value)));
}

function selectedExtendDuration(fallback = 10) {
  const value = Number(els.durationInput.value || fallback);
  if (!Number.isFinite(value)) return fallback;
  return Math.max(2, Math.min(10, Math.round(value)));
}

function selectedCount() {
  const value = Number(els.countInput.value || 1);
  if (!Number.isFinite(value)) return 1;
  return Math.max(1, Math.min(4, Math.round(value)));
}

async function savePrompt() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) {
    toastError("Write a prompt first.");
    return;
  }
  const suggested = prompt.slice(0, 40).trim() || "Prompt";
  const title = window.prompt("Prompt title", suggested);
  if (title === null) return;
  await api("/api/prompts", {
    method: "POST",
    body: JSON.stringify(basePayload(prompt, { mode: state.mode, title: title.trim() || suggested })),
  });
  toast("Prompt saved locally.");
  await loadState();
}

function closePromptEditor() {
  state.promptEditorOverlay?.remove();
  state.promptEditorOverlay = null;
}

function promptTranslationDirection(text) {
  const value = String(text || "");
  const koreanCount = (value.match(/[\u3131-\u318e\uac00-\ud7a3]/g) || []).length;
  const englishCount = (value.match(/[A-Za-z]/g) || []).length;
  return koreanCount > englishCount
    ? { from: "KOR", to: "ENG", target: "English" }
    : { from: "ENG", to: "KOR", target: "Korean" };
}

function translationButtonHtml(direction) {
  return `<span>${escapeHtml(direction.from)}</span>
    <svg class="translation-arrow-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14M14 7l5 5-5 5" />
    </svg>
    <span>${escapeHtml(direction.to)}</span>`;
}

function openPromptEditor(item, options = {}) {
  if (item && item.type !== "prompt") return;
  closePromptEditor();
  const create = Boolean(options.create || !item);
  const prompt = String(options.prompt ?? item?.prompt ?? "");
  const translation = String(options.translation ?? item?.translation ?? "");
  const title = String(options.title ?? item?.title ?? "");
  const direction = promptTranslationDirection(translation || prompt);
  const translationSource = translation ? "translation" : "original";
  const overlay = document.createElement("div");
  overlay.className = "prompt-editor-overlay";
  overlay.innerHTML = `
    <section class="prompt-editor-modal" role="dialog" aria-modal="true" aria-label="${create ? "New prompt" : "Edit prompt"}">
      <input class="prompt-editor-title" type="text" value="${escapeHtml(title)}" placeholder="Prompt title" aria-label="Prompt title" />
      <div class="prompt-editor-split">
        <textarea class="prompt-editor-text prompt-editor-original" aria-label="Prompt content" placeholder="Write a prompt...">${escapeHtml(prompt)}</textarea>
        <textarea class="prompt-editor-text prompt-editor-translation" aria-label="Translated prompt" placeholder="Translation appears here." readonly>${escapeHtml(translation)}</textarea>
      </div>
      <div class="prompt-editor-actions">
        <button class="ghost-button prompt-editor-translate" type="button" data-target-language="${escapeHtml(direction.target)}" aria-label="${escapeHtml(direction.from)} to ${escapeHtml(direction.to)}">${translationButtonHtml(direction)}</button>
        <div class="prompt-editor-actions-right">
          <button class="ghost-button prompt-editor-cancel" type="button">Cancel</button>
          <button class="primary-button prompt-editor-save" type="button">Save</button>
        </div>
      </div>
    </section>
  `;
  document.body.append(overlay);
  state.promptEditorOverlay = overlay;
  const modal = overlay.querySelector(".prompt-editor-modal");
  const titleInput = overlay.querySelector(".prompt-editor-title");
  const textInput = overlay.querySelector(".prompt-editor-original");
  const translationInput = overlay.querySelector(".prompt-editor-translation");
  const translateButton = overlay.querySelector(".prompt-editor-translate");
  const close = () => closePromptEditor();
  let dismissStartedOnOverlay = false;
  const setTranslationDirection = (next, source = "original") => {
    if (translateButton) {
      translateButton.innerHTML = translationButtonHtml(next);
      translateButton.dataset.targetLanguage = next.target;
      translateButton.dataset.translationSource = source;
      translateButton.setAttribute("aria-label", `${next.from} to ${next.to}`);
    }
  };
  const refreshTranslationDirection = () => {
    setTranslationDirection(promptTranslationDirection(textInput?.value || ""));
  };
  setTranslationDirection(direction, translationSource);
  overlay.addEventListener("pointerdown", (event) => {
    dismissStartedOnOverlay = event.target === overlay;
  });
  overlay.addEventListener("click", (event) => {
    if (dismissStartedOnOverlay && event.target === overlay) close();
    dismissStartedOnOverlay = false;
  });
  overlay.addEventListener("pointercancel", () => {
    dismissStartedOnOverlay = false;
  });
  textInput?.addEventListener("input", () => {
    refreshTranslationDirection();
    if (translationInput) translationInput.value = "";
  });
  translateButton?.addEventListener("click", () => {
    translatePromptEditor(textInput, translationInput, translateButton)
      .catch((error) => showErrorPanel("Translation failed", error.message));
  });
  overlay.querySelector(".prompt-editor-cancel")?.addEventListener("click", close);
  overlay.querySelector(".prompt-editor-save")?.addEventListener("click", () => {
    savePromptEditor(item, titleInput, textInput, translationInput, options).catch((error) => showErrorPanel("Prompt failed", error.message));
  });
  modal?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      savePromptEditor(item, titleInput, textInput, translationInput, options).catch((error) => showErrorPanel("Prompt failed", error.message));
    }
  });
  textInput?.focus();
}

async function translatePromptEditor(textInput, translationInput, button) {
  const promoteTranslation = button?.dataset.translationSource === "translation";
  const promotedText = String(translationInput?.value || "").trim();
  if (promoteTranslation && promotedText && textInput) {
    textInput.value = promotedText;
  }
  const text = String(textInput?.value || "").trim();
  if (!text) {
    toastError("Prompt content is empty.");
    return;
  }
  const targetLanguage = button?.dataset.targetLanguage || "Korean";
  if (button) button.disabled = true;
  try {
    const data = await api("/api/translate", {
      method: "POST",
      body: JSON.stringify({ text, target_language: targetLanguage }),
    });
    if (translationInput) translationInput.value = data.translation || "";
    if (button) {
      const next = targetLanguage === "Korean"
        ? { from: "Kor", to: "Eng", target: "English" }
        : { from: "Eng", to: "Kor", target: "Korean" };
      button.innerHTML = translationButtonHtml(next);
      button.dataset.targetLanguage = next.target;
      button.dataset.translationSource = "translation";
      button.setAttribute("aria-label", `${next.from} to ${next.to}`);
    }
  } finally {
    if (button) button.disabled = false;
  }
}

async function savePromptEditor(item, titleInput, textInput, translationInput, options = {}) {
  const prompt = String(textInput?.value || "").trim();
  const translation = String(translationInput?.value || "").trim();
  const suggested = prompt.slice(0, 40).trim() || "Prompt";
  const title = String(titleInput?.value || "").trim() || suggested;
  if (!prompt) {
    toastError("Prompt content is empty.");
    return;
  }
  if (item?.id) {
    const data = await api(`/api/items/${encodeURIComponent(item.id)}/update`, {
      method: "POST",
      body: JSON.stringify({ title, prompt, translation }),
    });
    const updated = data.item || { ...item, title, prompt, translation };
    const index = state.items.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) state.items[index] = { ...state.items[index], ...updated };
  } else {
    await api("/api/prompts", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        translation,
        title,
        mode: options.mode || "note",
        category: "Prompt",
        gallery_folder_id: state.workspaceFolderId || undefined,
      }),
    });
    await loadState();
  }
  closePromptEditor();
  renderGallery();
  toast(item?.id ? "Prompt updated." : "Prompt saved locally.");
}

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}

function readBlobAsDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read local image."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(blob);
  });
}

function collectFormStatus() {
  return {
    promptLength: els.promptInput.value.trim().length,
    imageFiles: sourceSummary(state.editImages),
    startImageFiles: fileSummary(els.startImageFile.files),
    startImageSource: state.startImage?.source || "",
    referenceImageFiles: sourceSummary(state.referenceImages),
    sourceVideoFiles: state.sourceVideo?.source === "file"
      ? fileSummary([state.sourceVideo.file])
      : fileSummary(els.sourceVideoFile.files),
    sourceVideoSource: state.sourceVideo?.source || "",
    sourceVideoTrimEnd: currentSourceVideoTrimEnd(),
    sourceTrimQuality: els.trimQualityInput.value || "high",
    imageModel: selectedImageModel(),
  };
}

function fileSummary(fileList) {
  return Array.from(fileList || []).map((file) => ({
    name: file.name,
    size: file.size,
    type: file.type,
  }));
}

function sourceSummary(sources) {
  return Array.from(sources || []).map((source) => ({
    name: source.name,
    size: source.size || 0,
    type: source.type || "image",
    source: source.source,
  }));
}

function formatBytes(size) {
  if (!Number.isFinite(size)) return "unknown size";
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function autoSizePromptInput() {
  if (!els.promptInput) return;
  if (!state.promptExpanded) {
    els.promptInput.style.height = "44px";
    return;
  }
  els.promptInput.style.height = "auto";
  const next = Math.min(220, Math.max(44, els.promptInput.scrollHeight));
  els.promptInput.style.height = `${next}px`;
}

function setPromptExpanded(expanded) {
  state.promptExpanded = Boolean(expanded);
  if (els.promptInput) {
    els.promptInput.wrap = state.promptExpanded ? "soft" : "off";
  }
  els.promptInput?.closest(".lab-composer")?.classList.toggle("prompt-expanded", state.promptExpanded);
  autoSizePromptInput();
  if (expanded) ensureDetailExtendComposerState();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderImageFileNames() {
  renderAttachmentTray();
}

function renderVideoFileNames() {
  renderImageSourceList(els.videoFileNames, state.referenceImages, "reference");
  renderAttachmentTray();
}

function toggleAttachmentTray(force) {
  const next = typeof force === "boolean" ? force : !state.attachmentTrayOpen;
  if (next && !state.attachmentTrayOpen) state.uploadHistoryVisibleCount = UPLOAD_HISTORY_PAGE_SIZE;
  state.attachmentTrayOpen = next;
  renderAttachmentTray();
}

function renderAttachmentTray() {
  if (!els.attachmentTray || !els.composerAttachBtn) return;
  els.attachmentTray.hidden = !state.attachmentTrayOpen;
  els.composerAttachBtn.textContent = state.attachmentTrayOpen ? "×" : "+";
  els.composerAttachBtn.classList.toggle("is-open", state.attachmentTrayOpen);
  els.composerAttachBtn.setAttribute("aria-label", state.attachmentTrayOpen ? "Close source image tray" : "Open source image tray");
  renderComposerAttachedList();
  renderUploadHistoryStrip();
}

function closeComposerTransientPanels() {
  closeCustomSelects();
  state.attachmentTrayOpen = false;
  state.uploadHistoryVisibleCount = UPLOAD_HISTORY_PAGE_SIZE;
  renderAttachmentTray();
  setPromptExpanded(false);
}

function renderUploadHistoryStrip(options = {}) {
  if (!els.uploadHistoryStrip) return;
  const uploads = Array.isArray(state.uploads) ? state.uploads : [];
  if (!uploads.length) {
    els.uploadHistoryStrip.onscroll = null;
    els.uploadHistoryStrip.onwheel = null;
    els.uploadHistoryStrip.innerHTML = `<p class="upload-history-empty">No uploaded images yet.</p>`;
    return;
  }
  const visibleCount = Math.min(
    uploads.length,
    Math.max(UPLOAD_HISTORY_PAGE_SIZE, Number(state.uploadHistoryVisibleCount || UPLOAD_HISTORY_PAGE_SIZE)),
  );
  state.uploadHistoryVisibleCount = visibleCount;
  const visibleUploads = uploads.slice(0, visibleCount);
  const currentModeSources = state.mode === "image" || state.mode === "analyze"
    ? state.editImages
    : state.mode === "video"
    ? [...(state.startImage ? [state.startImage] : []), ...state.referenceImages]
    : [];
  const attachedUrls = new Set(currentModeSources.map((source) => source.previewUrl).filter(Boolean));
  els.uploadHistoryStrip.innerHTML = visibleUploads.map((upload, index) => `
    <div class="upload-history-thumb-wrap${attachedUrls.has(upload.local_url) ? " active" : ""}">
      <button class="upload-history-thumb" type="button" data-upload-index="${index}">
        <img src="${escapeHtml(upload.local_url)}" alt="${escapeHtml(upload.name || upload.title || "Uploaded image")}" loading="lazy" decoding="async" />
        ${attachedUrls.has(upload.local_url) ? `<span class="upload-selected-check">✓</span>` : ""}
      </button>
    </div>
  `).join("");
  if (typeof options.restoreScrollTop === "number") {
    els.uploadHistoryStrip.scrollTop = options.restoreScrollTop;
  }
  els.uploadHistoryStrip.querySelectorAll(".upload-history-thumb").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const upload = uploads[Number(button.dataset.uploadIndex)];
      toggleUploadImageForCurrentMode(upload).catch((error) => showErrorPanel("Image failed", error.message));
    });
  });
  const maybeLoadMore = (scrollToMore = false) => {
    if (state.uploadHistoryVisibleCount >= uploads.length) return false;
    const strip = els.uploadHistoryStrip;
    const nextScrollTop = scrollToMore
      ? Math.min(strip.scrollTop + strip.clientHeight, Math.max(0, strip.scrollHeight - strip.clientHeight))
      : strip.scrollTop;
    state.uploadHistoryVisibleCount = Math.min(uploads.length, state.uploadHistoryVisibleCount + UPLOAD_HISTORY_PAGE_SIZE);
    renderUploadHistoryStrip({ restoreScrollTop: nextScrollTop });
    return true;
  };
  els.uploadHistoryStrip.onscroll = () => {
    const strip = els.uploadHistoryStrip;
    if (strip.scrollTop + strip.clientHeight >= strip.scrollHeight - 24) maybeLoadMore(false);
  };
  els.uploadHistoryStrip.onwheel = (event) => {
    if (event.deltaY <= 0) return;
    const strip = els.uploadHistoryStrip;
    const canScroll = strip.scrollHeight > strip.clientHeight + 1;
    const nearBottom = strip.scrollTop + strip.clientHeight >= strip.scrollHeight - 24;
    if (!canScroll || nearBottom) {
      const loaded = maybeLoadMore(!canScroll);
      if (loaded && !canScroll) event.preventDefault();
    }
  };
}

function composerAttachedSources() {
  if (state.mode === "video") {
    return [
      ...(state.startImage ? [{ ...state.startImage, kind: "start", index: 0, label: "Start Image" }] : []),
      ...state.referenceImages.map((source, index) => ({ ...source, kind: "reference", index, label: "Reference Image" })),
    ];
  }
  if (state.mode === "image" || state.mode === "analyze") {
    return state.editImages.map((source, index) => ({ ...source, kind: "edit", index, label: "Source Image" }));
  }
  return [];
}

function renderComposerAttachedList() {
  if (!els.imageFileNames) return;
  const sources = composerAttachedSources();
  if (!sources.length) {
    els.imageFileNames.innerHTML = "";
    return;
  }
  els.imageFileNames.innerHTML = sources.map((source) => `
    <div class="composer-attached-thumb ${source.kind === "start" ? "is-start" : ""}${source.kind === "reference" && source.index === 0 && sources.some((candidate) => candidate.kind === "start") ? " after-start" : ""}${source.kind === "edit" && source.index === 1 ? " after-source" : ""}" data-kind="${escapeHtml(source.kind)}" data-index="${source.index}">
      <button class="composer-attached-preview image-preview-trigger" type="button" data-preview-src="${escapeHtml(source.previewUrl)}" data-preview-title="${escapeHtml(source.name)}">
        <img src="${escapeHtml(source.previewUrl)}" alt="${escapeHtml(source.name)}" />
      </button>
      <button class="cancel-attached-image" type="button" data-kind="${escapeHtml(source.kind)}" data-index="${source.index}" title="Cancel attachment" aria-label="Cancel attachment">×</button>
    </div>
  `).join("");
  els.imageFileNames.querySelectorAll(".cancel-attached-image").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      cancelComposerAttachment(button.dataset.kind, Number(button.dataset.index));
    });
  });
}

function cancelComposerAttachment(kind, index) {
  if (kind === "start") {
    clearStartImage();
    return;
  }
  if (kind === "reference") {
    removeImageSource("reference", index);
    return;
  }
  removeImageSource("edit", index);
}

function renderImageSourceList(container, sources, kind) {
  if (!sources.length) {
    container.innerHTML = "";
    return;
  }
  const label = kind === "edit" ? "Source Image" : "Reference Image";
  container.innerHTML = sources.map((source, index) => `
    <div class="source-image-row" data-source-kind="${escapeHtml(kind)}" data-source-index="${index}">
      <button class="source-image-thumb image-preview-trigger" type="button" data-preview-src="${escapeHtml(source.previewUrl)}" data-preview-title="${escapeHtml(source.name)}">
        <img src="${escapeHtml(source.previewUrl)}" alt="${escapeHtml(source.name)}" />
      </button>
      <div>
        <strong title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</strong>
        <small>${label}</small>
      </div>
      <button class="clear-source-image" type="button" data-kind="${kind}" data-index="${index}" title="Remove image" aria-label="Remove image">x</button>
    </div>
  `).join("");
  container.querySelectorAll(".clear-source-image").forEach((button) => {
    button.addEventListener("click", () => removeImageSource(button.dataset.kind, Number(button.dataset.index)));
  });
  container.querySelectorAll(".source-image-row").forEach((row) => {
    row.addEventListener("dragover", (event) => {
      event.preventDefault();
      row.classList.add("drag-over");
    });
    row.addEventListener("dragleave", () => {
      row.classList.remove("drag-over");
    });
    row.addEventListener("drop", (event) => {
      handleImageSourceReplaceDrop(event, row.dataset.sourceKind, Number(row.dataset.sourceIndex))
        .catch((error) => showErrorPanel("Image failed", error.message));
    });
  });
}

function removeImageSource(kind, index) {
  const list = kind === "reference" ? state.referenceImages : state.editImages;
  const [removed] = list.splice(index, 1);
  revokeImageSource(removed);
  if (kind === "edit" && removed && imageSourceAlreadyAttached(removed, [state.startImage])) {
    clearStartImage();
  }
  if (kind === "reference") renderVideoFileNames();
  else renderImageFileNames();
}

function revokeImageSource(source) {
  if (source?.source === "file" && source.previewUrl?.startsWith("blob:")) {
    URL.revokeObjectURL(source.previewUrl);
  }
}

function uploadMatchesSource(upload, source) {
  if (!upload || !source) return false;
  return Boolean(
    (source.uploadId && source.uploadId === upload.id)
    || (upload.local_url && (source.previewUrl === upload.local_url || source.value === upload.local_url)),
  );
}

function uploadAttachmentMatch(upload) {
  if (!upload) return null;
  if (state.mode === "video") {
    if (uploadMatchesSource(upload, state.startImage)) return { kind: "start", index: 0 };
    const referenceIndex = state.referenceImages.findIndex((source) => uploadMatchesSource(upload, source));
    if (referenceIndex >= 0) return { kind: "reference", index: referenceIndex };
  }
  if (state.mode === "image" || state.mode === "analyze") {
    const editIndex = state.editImages.findIndex((source) => uploadMatchesSource(upload, source));
    if (editIndex >= 0) return { kind: "edit", index: editIndex };
  }
  return null;
}

function removeUploadAttachment(upload, match = uploadAttachmentMatch(upload)) {
  if (!match) return false;
  if (match.kind === "start") {
    clearStartImage();
  } else if (match.kind === "reference") {
    removeImageSource("reference", match.index);
  } else if (match.kind === "edit") {
    const source = state.editImages[match.index];
    removeImageSource("edit", match.index);
    if (source && uploadMatchesSource(upload, state.startImage)) clearStartImage();
  }
  state.attachmentTrayOpen = true;
  renderAttachmentTray();
  return true;
}

async function toggleUploadImageForCurrentMode(upload) {
  const match = uploadAttachmentMatch(upload);
  if (match) {
    removeUploadAttachment(upload, match);
    return;
  }
  await addUploadImageToCurrentMode(upload, { keepTrayOpen: true });
  state.attachmentTrayOpen = true;
  renderAttachmentTray();
}

function detachUploadImage(upload) {
  state.editImages = state.editImages.filter((source) => {
    const match = uploadMatchesSource(upload, source);
    if (match) revokeImageSource(source);
    return !match;
  });
  state.referenceImages = state.referenceImages.filter((source) => {
    const match = uploadMatchesSource(upload, source);
    if (match) revokeImageSource(source);
    return !match;
  });
  if (uploadMatchesSource(upload, state.startImage)) {
    revokeStartImagePreview();
    state.startImage = null;
    els.startImageFile.value = "";
  }
  renderStartImagePreview();
  renderVideoFileNames();
  renderImageFileNames();
}

async function deleteUploadedImage(upload) {
  if (!upload?.id) return;
  const data = await api("/api/uploads/images/delete", {
    method: "POST",
    body: JSON.stringify({ id: upload.id, file: upload.file || undefined }),
  });
  detachUploadImage(upload);
  state.uploads = Array.isArray(data.uploads)
    ? data.uploads
    : state.uploads.filter((candidate) => candidate.id !== upload.id);
  renderAttachmentTray();
}

async function addEditImageFiles(files) {
  const previousLength = state.editImages.length;
  await addImageFiles(files, state.editImages, 3);
  els.imageFiles.value = "";
  const firstAdded = state.editImages.slice(previousLength)[0];
  if (firstAdded) setStartImageFromImageSource(firstAdded);
  renderImageFileNames();
}

async function addReferenceImageFiles(files) {
  await addImageFiles(files, state.referenceImages, 7);
  els.referenceImageFiles.value = "";
  renderVideoFileNames();
}

async function addVideoImageFiles(files) {
  const imageFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  for (const file of imageFiles) {
    const source = await imageSourceFromFile(file);
    if (!addVideoImageSource(source)) break;
  }
  els.imageFiles.value = "";
  els.startImageFile.value = "";
  els.referenceImageFiles.value = "";
  renderVideoFileNames();
}

function addVideoImageSource(source) {
  if (!state.startImage) {
    setStartImageSource(source);
    return "start";
  }
  if (imageSourceAlreadyAttached(source, [state.startImage])) {
    revokeImageSource(source);
    return "exists";
  }
  if (imageSourceAlreadyAttached(source, state.referenceImages)) {
    revokeImageSource(source);
    return "exists";
  }
  if (state.referenceImages.length >= 7) {
    toastError("Up to 7 Reference Images");
    revokeImageSource(source);
    return "";
  }
  state.referenceImages.push(source);
  renderVideoFileNames();
  return "reference";
}

function imageSourceAlreadyAttached(source, list) {
  return Array.from(list || []).some((candidate) => (
    candidate.uploadId && source.uploadId && candidate.uploadId === source.uploadId
  ) || (
    candidate.previewUrl && source.previewUrl && candidate.previewUrl === source.previewUrl
  ) || (
    candidate.value && source.value && candidate.value === source.value
  ));
}

async function addImageFiles(files, target, limit) {
  const imageFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  for (const file of imageFiles) {
    if (target.length >= limit) {
      toastError(limit === 7 ? "Up to 7 Reference Images" : "Up to 3 Source Images");
      break;
    }
    target.push(await imageSourceFromFile(file));
  }
}

async function addEditImageFromLibrary(item) {
  if (!item || item.type !== "image" || !item.local_url) {
    toastError("Only local image results can be used as a source image.");
    return;
  }
  if (state.editImages.length >= 3) {
    toastError("Up to 3 Source Images");
    return;
  }
  const source = await imageSourceFromLibraryItem(item);
  state.editImages.push(source);
  setStartImageFromImageSource(source);
  renderImageFileNames();
  toast("Image attached as Source Image.");
}

function clearDetailAutoEditImages() {
  const previousLength = state.editImages.length;
  state.editImages = state.editImages.filter((source) => {
    const keep = source.source !== "detail-auto";
    if (!keep) revokeImageSource(source);
    return keep;
  });
  if (state.editImages.length !== previousLength) {
    renderImageFileNames();
  }
}

function setEditImageFromDetailItem(item) {
  if (!item || item.type !== "image" || !item.local_url) return;
  clearDetailAutoEditImages();
  if (imageSourceAlreadyAttached({ value: item.local_url, previewUrl: item.local_url }, state.editImages)) {
    renderImageFileNames();
    return;
  }
  state.editImages.unshift({
    id: imageSourceId(),
    source: "detail-auto",
    name: item.title || "Source Image",
    type: item.mime || "image",
    size: 0,
    value: item.local_url,
    previewUrl: item.local_url,
    itemId: item.id,
  });
  while (state.editImages.length > 3) {
    revokeImageSource(state.editImages.pop());
  }
  renderImageFileNames();
}

function setEditImageFromDetailSource(source) {
  const imageSource = detailSourceAsImageSource(source);
  if (!imageSource) return;
  state.editImages = state.editImages.filter((candidate) => {
    const keep = candidate.source !== "detail-source" && candidate.source !== "detail-auto";
    if (!keep) revokeImageSource(candidate);
    return keep;
  });
  if (!imageSourceAlreadyAttached(imageSource, state.editImages)) {
    state.editImages.unshift(imageSource);
  }
  while (state.editImages.length > 3) {
    revokeImageSource(state.editImages.pop());
  }
  renderImageFileNames();
}

async function addReferenceImageFromLibrary(item) {
  if (!item || item.type !== "image" || !item.local_url) {
    toastError("Only local image results can be used as a reference image.");
    return;
  }
  if (state.referenceImages.length >= 7) {
    toastError("Up to 7 Reference Images");
    return;
  }
  state.referenceImages.push(await imageSourceFromLibraryItem(item));
  renderVideoFileNames();
  toast("Image attached as Reference Image.");
}

async function addVideoImageFromLibrary(item) {
  const source = await imageSourceFromLibraryItem(item);
  const role = addVideoImageSource(source);
  if (role === "start") toast("Image set as Start image.");
  if (role === "reference") toast("Image attached as Reference Image.");
}

async function imageSourceFromFile(file) {
  const dataUrl = await readAsDataUrl(file);
  let saved = null;
  try {
    saved = await saveUploadedImage(file, dataUrl);
  } catch (error) {
    console.warn("Could not save upload image history", error);
  }
  return {
    id: imageSourceId(),
    source: saved ? "upload" : "file",
    name: saved?.name || file.name,
    type: file.type || "image",
    size: file.size || 0,
    value: saved?.local_url || dataUrl,
    previewUrl: saved?.local_url || URL.createObjectURL(file),
    uploadId: saved?.id || "",
  };
}

async function saveUploadedImage(file, dataUrl) {
  const data = await api("/api/uploads/images", {
    method: "POST",
    body: JSON.stringify({
      images: [dataUrl],
      names: [file?.name || "Source Image"],
      gallery_folder_id: state.workspaceFolderId || undefined,
    }),
  });
  if (Array.isArray(data.uploads)) {
    state.uploads = data.uploads;
    renderAttachmentTray();
  }
  return Array.isArray(data.saved) ? data.saved[0] : null;
}

async function imageSourceFromUpload(upload) {
  if (!upload?.local_url) throw new Error("Uploaded image is missing.");
  return {
    id: imageSourceId(),
    source: "upload",
    name: upload.name || upload.title || "Uploaded image",
    type: upload.mime || "image",
    size: upload.size || 0,
    value: upload.local_url,
    previewUrl: upload.local_url,
    uploadId: upload.id || "",
  };
}

async function addUploadImageToCurrentMode(upload, options = {}) {
  const source = await imageSourceFromUpload(upload);
  if (state.mode === "video") {
    addVideoImageSource(source);
    if (options.keepTrayOpen) state.attachmentTrayOpen = true;
    return;
  }
  if (state.mode === "extend") {
    if (options.keepTrayOpen) state.attachmentTrayOpen = true;
    renderAttachmentTray();
    return;
  }
  if (state.editImages.length >= 3) {
    toastError("Up to 3 Source Images");
    return;
  }
  state.editImages.push(source);
  setStartImageFromImageSource(source);
  if (options.keepTrayOpen) state.attachmentTrayOpen = true;
  renderImageFileNames();
}

async function imageSourceFromLibraryItem(item) {
  if (!item || item.type !== "image" || !item.local_url) {
    throw new Error("Only local image results can be used here.");
  }
  const response = await fetch(item.local_url);
  if (!response.ok) throw new Error("Could not read the local library image.");
  const blob = await response.blob();
  return {
    id: imageSourceId(),
    source: "library",
    name: item.title || "Library image",
    type: blob.type || item.mime || "image",
    size: blob.size || 0,
    value: await readBlobAsDataUrl(blob),
    previewUrl: item.local_url,
  };
}

function imageSourceList(kind) {
  return kind === "reference" ? state.referenceImages : state.editImages;
}

function renderImageSourceKind(kind) {
  if (kind === "reference") renderVideoFileNames();
  else renderImageFileNames();
}

async function handleImageSourceReplaceDrop(event, kind, index) {
  event.preventDefault();
  event.stopPropagation();
  const row = event.currentTarget instanceof Element ? event.currentTarget : null;
  row?.classList.remove("drag-over");
  if (!Number.isInteger(index) || index < 0) return;

  const file = Array.from(event.dataTransfer.files || []).find((candidate) => candidate.type.startsWith("image/"));
  let replacement = null;
  if (file) {
    replacement = await imageSourceFromFile(file);
  } else {
    const itemId = event.dataTransfer.getData("application/x-grok-item-id") || event.dataTransfer.getData("text/plain");
    const item = galleryItemById(itemId);
    replacement = await imageSourceFromLibraryItem(item);
  }

  const list = imageSourceList(kind);
  if (!list[index]) return;
  const [old] = list.splice(index, 1, replacement);
  revokeImageSource(old);
  renderImageSourceKind(kind);
  toast("Image replaced.");
}

function imageSourceId() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function openImagePreview(src, title = "Image preview") {
  if (!src) return;
  closeImagePreview();
  const overlay = document.createElement("div");
  overlay.className = "image-preview-overlay";
  overlay.innerHTML = `
    <div class="image-preview-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
      <img src="${escapeHtml(src)}" alt="${escapeHtml(title)}" />
    </div>
  `;
  document.body.append(overlay);
  state.previewOverlay = overlay;
  overlay.addEventListener("click", closeImagePreview);
}

function closeImagePreview(options = {}) {
  const overlay = state.previewOverlay;
  if (!overlay) return;
  const fullscreenElement = document.fullscreenElement;
  const shouldExitFullscreen = !options.skipExitFullscreen
    && fullscreenElement
    && (fullscreenElement === overlay || overlay.contains(fullscreenElement));
  if (overlay._fullscreenChangeHandler) {
    document.removeEventListener("fullscreenchange", overlay._fullscreenChangeHandler);
  }
  overlay.remove();
  state.previewOverlay = null;
  if (shouldExitFullscreen) {
    document.exitFullscreen?.().catch(() => {});
  }
}

function blockPromptDrop(event) {
  event.preventDefault();
  event.stopPropagation();
  if (event.type === "drop") {
    toastError("Images cannot be dropped into the prompt box.");
  }
}

async function setStartImageFromFile(file) {
  const source = await imageSourceFromFile(file);
  setStartImageSource(source);
}

function startImagePreviewForSource(source) {
  const value = source?.value || "";
  if (source?.previewUrl) return source.previewUrl;
  if (value.startsWith("/media/") || value.startsWith("data:") || value.startsWith("http")) return value;
  return "";
}

function setStartImageFromImageSource(source) {
  if (!source?.value) return;
  setStartImageSource(source);
}

function setStartImageSource(source) {
  revokeStartImagePreview();
  state.startImage = {
    source: source.source || "upload",
    value: source.value,
    previewUrl: startImagePreviewForSource(source),
    name: source.name,
    uploadId: source.uploadId || "",
    itemId: source.itemId || "",
  };
  els.startImageFile.value = "";
  renderStartImagePreview();
  renderVideoFileNames();
  renderAttachmentTray();
}

function setStartImageFromDetailItem(item) {
  if (!item || item.type !== "image" || !item.local_url) return;
  if (state.startImage?.source === "detail-auto" && state.startImage.itemId === item.id) return;
  revokeStartImagePreview();
  state.startImage = {
    source: "detail-auto",
    value: item.local_url,
    previewUrl: item.local_url,
    name: item.title || "Start Image",
    itemId: item.id,
  };
  els.startImageFile.value = "";
  renderStartImagePreview();
  renderVideoFileNames();
  renderAttachmentTray();
}

function setStartImageFromDetailSource(source) {
  const imageSource = detailSourceAsImageSource(source);
  if (!imageSource) return;
  if (state.startImage?.source === "detail-source" && state.startImage.previewUrl === imageSource.previewUrl) {
    renderAttachmentTray();
    return;
  }
  setStartImageSource(imageSource);
}

function setStartImageFromLibrary(item) {
  if (!item || item.type !== "image" || !item.local_url) {
    toastError("Only local image results can be used as a start image.");
    return;
  }
  revokeStartImagePreview();
  state.startImage = {
    source: "library",
    value: item.local_url,
    previewUrl: item.local_url,
    name: item.title || "Library image",
    itemId: item.id || "",
  };
  els.startImageFile.value = "";
  setMode("video");
  renderStartImagePreview();
  renderVideoFileNames();
  renderAttachmentTray();
  toast("Image set as Start image.");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function revokeStartImagePreview(source = state.startImage) {
  if (source?.source === "file" && source.previewUrl?.startsWith("blob:")) {
    URL.revokeObjectURL(source.previewUrl);
  }
}

function clearStartImage(options = {}) {
  const previous = state.startImage;
  revokeStartImagePreview(previous);
  state.startImage = null;
  if (options.promoteReference && state.referenceImages.length) {
    state.startImage = state.referenceImages.shift();
  }
  els.startImageFile.value = "";
  renderStartImagePreview();
  renderVideoFileNames();
}

function renderStartImagePreview() {
  if (!state.startImage) {
    els.startImagePreview.hidden = true;
    els.startImagePreview.innerHTML = "";
    return;
  }
  els.startImagePreview.hidden = false;
  els.startImagePreview.innerHTML = `
    <button class="start-image-thumb image-preview-trigger" type="button" data-preview-src="${escapeHtml(state.startImage.previewUrl)}" data-preview-title="${escapeHtml(state.startImage.name)}">
      <img src="${escapeHtml(state.startImage.previewUrl)}" alt="Start image preview" />
    </button>
    <div>
      <strong title="${escapeHtml(state.startImage.name)}">${escapeHtml(state.startImage.name)}</strong>
    </div>
    <button class="clear-start-image" type="button" title="Clear start image" aria-label="Clear start image">x</button>
  `;
  els.startImagePreview.querySelector(".clear-start-image").addEventListener("click", clearStartImage);
  els.startImagePreview.ondragover = (event) => {
    event.preventDefault();
    els.startImagePreview.classList.add("drag-over");
  };
  els.startImagePreview.ondragleave = () => {
    els.startImagePreview.classList.remove("drag-over");
  };
  els.startImagePreview.ondrop = (event) => {
    handleStartImageDrop(event, els.startImagePreview).catch((error) => toastError(error.message));
  };
}

function revokeSourceVideoPreview() {
  if (state.sourceVideo?.source === "file" && state.sourceVideo.previewUrl?.startsWith("blob:")) {
    URL.revokeObjectURL(state.sourceVideo.previewUrl);
  }
}

function setSourceVideoFromLibrary(item, options = {}) {
  if (!item || item.type !== "video" || !item.local_url) {
    toastError("Only local video results can be used for Extend.");
    return;
  }
  revokeSourceVideoPreview();
  state.sourceVideo = {
    source: "library",
    id: item.id,
    previewUrl: item.local_url,
    name: "Video",
  };
  state.selectedVideoId = item.id;
  els.sourceVideoSelect.value = item.id;
  els.sourceVideoFile.value = "";
  if (!options.skipMode) setMode("extend", { skipDetailExtend: options.skipDetailExtend });
  renderSourceVideoPreview();
  if (!options.silent) toast("Video attached for extension.");
  if (options.scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function setSourceVideoFromFile(file) {
  if (!file || !file.type.startsWith("video/")) {
    toastError("Choose an MP4 or video file.");
    return;
  }
  revokeSourceVideoPreview();
  state.sourceVideo = {
    source: "file",
    file,
    previewUrl: URL.createObjectURL(file),
    name: file.name,
  };
  state.selectedVideoId = "";
  els.sourceVideoSelect.value = "";
  renderSourceVideoPreview();
}

function clearSourceVideo() {
  revokeSourceVideoPreview();
  state.sourceVideo = null;
  state.selectedVideoId = "";
  els.sourceVideoSelect.value = "";
  els.sourceVideoFile.value = "";
  renderSourceVideoPreview();
}

function renderSourceVideoPreview() {
  if (!state.sourceVideo) {
    els.sourceVideoPreview.hidden = true;
    els.sourceVideoPreview.innerHTML = "";
    return;
  }
  const label = state.sourceVideo.source === "library" ? "Library" : "Uploaded MP4";
  els.sourceVideoPreview.hidden = false;
  els.sourceVideoPreview.innerHTML = `
    ${videoPlayerHtml(state.sourceVideo.previewUrl, "Video", {
      compact: true,
      extraClass: "source-preview-video-wrap",
      videoClass: "source-preview-video",
    })}
    <div>
      <strong title="${escapeHtml(state.sourceVideo.name)}">${escapeHtml(state.sourceVideo.name)}</strong>
      <small>${escapeHtml(label)}</small>
    </div>
    <button class="clear-source-video" type="button" title="Clear local video" aria-label="Clear local video">x</button>
  `;
  els.sourceVideoPreview.querySelector(".clear-source-video").addEventListener("click", clearSourceVideo);
  els.sourceVideoPreview.ondragover = (event) => {
    event.preventDefault();
    els.sourceVideoPreview.classList.add("drag-over");
  };
  els.sourceVideoPreview.ondragleave = () => {
    els.sourceVideoPreview.classList.remove("drag-over");
  };
  els.sourceVideoPreview.ondrop = (event) => {
    handleSourceVideoDrop(event, els.sourceVideoPreview);
  };
  bindCustomVideoPlayers();
}

function currentSourceVideoTrimEnd() {
  const video = els.sourceVideoPreview.querySelector(".source-preview-video");
  if (!video || video.paused === false) return "";
  const current = Number(video.currentTime);
  const duration = Number(video.duration);
  if (!Number.isFinite(current) || current <= 0.25) return "";
  if (Number.isFinite(duration) && current >= duration - 0.25) return "";
  return Number(current.toFixed(3));
}

async function handleStartImageDrop(event, target = els.startImageDrop) {
  event.preventDefault();
  target.classList.remove("drag-over");
  const file = event.dataTransfer.files?.[0];
  if (file && file.type.startsWith("image/")) {
    await setStartImageFromFile(file);
    renderVideoFileNames();
    return;
  }
  const itemId = event.dataTransfer.getData("text/plain");
  const item = galleryItemById(itemId);
  setStartImageFromLibrary(item);
}

async function handleEditImageDrop(event, target = els.imageSourceDrop) {
  event.preventDefault();
  target.classList.remove("drag-over");
  const files = Array.from(event.dataTransfer.files || []).filter((file) => file.type.startsWith("image/"));
  if (files.length) {
    await addComposerImageFiles(files);
    return;
  }
  const itemId = event.dataTransfer.getData("application/x-grok-item-id") || event.dataTransfer.getData("text/plain");
  const item = galleryItemById(itemId);
  if (state.mode === "video") {
    await addVideoImageFromLibrary(item);
  } else {
    await addEditImageFromLibrary(item);
  }
}

async function addComposerImageFiles(files) {
  const imageFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  if (!imageFiles.length) return;
  if (state.mode === "video") {
    await addVideoImageFiles(imageFiles);
    return;
  }
  if (state.mode === "extend") {
    renderAttachmentTray();
    return;
  }
  await addEditImageFiles(imageFiles);
}

function initializeBrowserHistory() {
  const initialUrl = new URL(window.location.href);
  const requestedDetailId = initialUrl.searchParams.get("detail") || "";
  const folderGallery = initialUrl.searchParams.get("gallery") === "1";
  const imagineLibrary = initialUrl.searchParams.get("imagine") === "1";
  const initialFolderId = initialUrl.searchParams.get("folder") || "";
  state.workspaceFolderId = requestedDetailId ? initialFolderId : "";
  state.imagineRemoteView = imagineLibrary
    ? normalizeImagineRemoteView(initialUrl.searchParams.get("imagine_view"))
    : IMAGINE_REMOTE_VIEW_ALL;
  state.imaginePortfolioTypeFilter = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL
    ? normalizeImaginePortfolioTypeFilter(initialUrl.searchParams.get("imagine_portfolio_type"))
    : IMAGINE_PORTFOLIO_TYPE_ALL;
  state.imagineAllFilesTypeFilter = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES
    ? normalizeImagineAllFilesTypeFilter(initialUrl.searchParams.get("imagine_all_files_type"))
    : IMAGINE_ALL_FILES_TYPE_ALL;
  state.imagineDiscoverTypeFilter = state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER
    ? normalizeImagineDiscoverTypeFilter(initialUrl.searchParams.get("imagine_discover_type"))
    : IMAGINE_DISCOVER_TYPE_ALL;
  state.view = requestedDetailId ? "detail" : (imagineLibrary ? "imagine-library" : (folderGallery ? "folder-gallery" : "gallery"));
  history.replaceState(
    {
      ...history.state,
      grokStudioView: state.view,
      detailItemId: requestedDetailId,
      detailNavView: history.state?.detailNavView || state.detailNavView,
      detailNavFilter: history.state?.detailNavFilter || history.state?.galleryFilter || state.detailNavFilter,
      workspaceFolderId: state.workspaceFolderId,
      imagineRemoteView: state.imagineRemoteView,
      imaginePortfolioTypeFilter: state.imaginePortfolioTypeFilter,
      imagineDiscoverTypeFilter: state.imagineDiscoverTypeFilter,
      imagineAllFilesTypeFilter: state.imagineAllFilesTypeFilter,
    },
    "",
    requestedDetailId ? detailHistoryUrl(requestedDetailId) : (imagineLibrary ? workspaceHistoryUrl({
      imagineLibrary: true,
      imagineRemoteView: state.imagineRemoteView,
      imaginePortfolioType: state.imaginePortfolioTypeFilter,
      imagineDiscoverType: state.imagineDiscoverTypeFilter,
      imagineAllFilesType: state.imagineAllFilesTypeFilter,
    }) : (folderGallery ? workspaceHistoryUrl({ folderGallery: true }) : workspaceHistoryUrl())),
  );
  window.addEventListener("popstate", (event) => {
    const url = new URL(window.location.href);
    const urlDetailId = url.searchParams.get("detail") || "";
    if (event.state?.grokStudioAccount) {
      showAccountScreen(true, { fromHistory: true });
      return;
    }
    if (state.accountScreenVisible) {
      showAccountScreen(false, { fromHistory: true });
    }
    state.workspaceFolderId = String(event.state?.workspaceFolderId ?? url.searchParams.get("folder") ?? "");
    if (event.state?.grokStudioView === "folder-gallery" || url.searchParams.get("gallery") === "1") {
      openFolderGallery({ fromHistory: true });
      return;
    }
    if (event.state?.grokStudioView === "imagine-library" || url.searchParams.get("imagine") === "1") {
      openImagineLibrary({
        fromHistory: true,
        remoteView: event.state?.imagineRemoteView || url.searchParams.get("imagine_view"),
        portfolioType: event.state?.imaginePortfolioTypeFilter || url.searchParams.get("imagine_portfolio_type"),
        discoverType: event.state?.imagineDiscoverTypeFilter || url.searchParams.get("imagine_discover_type"),
        allFilesType: event.state?.imagineAllFilesTypeFilter || url.searchParams.get("imagine_all_files_type"),
      });
      return;
    }
    const itemId = event.state?.grokStudioView === "detail"
      ? String(event.state.detailItemId || urlDetailId)
      : urlDetailId;
    if (itemId && galleryItemById(itemId)) {
      openDetail(itemId, { fromHistory: true, navContext: detailNavContextFromHistory(event.state) });
      return;
    }
    closeDetail({ fromHistory: true });
    state.view = "gallery";
    syncWorkspaceView();
    renderGallery();
  });
}

async function handleReferenceImageDrop(event, target = els.referenceImageDrop) {
  event.preventDefault();
  target.classList.remove("drag-over");
  const files = Array.from(event.dataTransfer.files || []).filter((file) => file.type.startsWith("image/"));
  if (files.length) {
    await addReferenceImageFiles(files);
    return;
  }
  const itemId = event.dataTransfer.getData("application/x-grok-item-id") || event.dataTransfer.getData("text/plain");
  const item = galleryItemById(itemId);
  await addReferenceImageFromLibrary(item);
}

function handleSourceVideoDrop(event, target = els.sourceVideoDrop) {
  event.preventDefault();
  target.classList.remove("drag-over");
  const file = event.dataTransfer.files?.[0];
  if (file && file.type.startsWith("video/")) {
    setSourceVideoFromFile(file);
    return;
  }
  const itemId = event.dataTransfer.getData("application/x-grok-item-id") || event.dataTransfer.getData("text/plain");
  const item = galleryItemById(itemId);
  setSourceVideoFromLibrary(item);
}

function bindEvents() {
  setSidebarCollapsed(state.sidebarCollapsed);
  window.addEventListener("resize", () => {
    updateSidebarTogglePosition();
    if (state.view === "folder-gallery") {
      schedulePrimaryFolderListRows();
      scheduleSecondaryFolderGridRows();
    }
  });
  window.addEventListener("scroll", maybeLoadNextImagineRemotePage, { passive: true });
  els.imagineGallery?.addEventListener("scroll", maybeLoadNextImagineRemotePage, { passive: true });
  window.addEventListener("wheel", handleImagineRemoteWheel, { passive: true });
  els.imagineGallery?.addEventListener("wheel", handleImagineRemoteWheel, { passive: true });
  initCustomSelects();
  els.sidebarCloseBtn.addEventListener("click", () => setSidebarCollapsed(!state.sidebarCollapsed));
  els.sidebarOpenBtn.addEventListener("click", () => setSidebarCollapsed(false));
  els.brandHomeBtn?.addEventListener("click", () => openPrimaryHome());
  els.titleHomeBtn?.addEventListener("click", () => openPrimaryHome());
  els.galleryNavBtn?.addEventListener("click", () => openFolderGallery());
  els.imagineNavBtn?.addEventListener("click", () => openImagineLibrary());
  document.querySelectorAll("[data-gallery-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      sortSecondaryGalleryFolders(button.dataset.gallerySort || "abc")
        .catch((error) => toastError(error.message));
    });
  });
  els.saveGallerySortBtn?.addEventListener("click", () => {
    saveCurrentGallerySort().catch((error) => toastError(error.message));
  });
  els.collectionHeadingBtn?.addEventListener("click", () => {
    state.galleryCollectionSelected = true;
    state.selectedPrimaryFolderId = "";
    state.selectedSecondaryFolderId = "";
    renderFolderGallery();
  });
  els.makeFolderBtn?.addEventListener("click", () => {
    makeGalleryFolder().catch((error) => toastError(error.message));
  });
  els.renameFolderBtn?.addEventListener("click", () => {
    renameSelectedGalleryFolder().catch((error) => toastError(error.message));
  });
  els.deleteFolderBtn?.addEventListener("click", () => {
    deleteSelectedGalleryFolder().catch((error) => toastError(error.message));
  });
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => {
    showAccountScreen(false);
    setMode(tab.dataset.mode, { userSelect: true });
  }));
  $$(".nav-stack .nav-item[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      showAccountScreen(false);
      const previousView = state.view;
      if (state.view === "detail") closeDetail({ fromHistory: true });
      if (state.view === "folder-gallery" || state.view === "imagine-library") state.view = "gallery";
      state.workspaceFolderId = "";
      state.filter = button.dataset.filter;
      $$(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
      syncWorkspaceView();
      renderGallery();
      syncGalleryRouteAfterFilter(previousView);
    });
  });
  $$("[data-workspace-media-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!state.workspaceFolderId) return;
      showAccountScreen(false);
      const previousView = state.view;
      if (state.view === "detail") closeDetail({ fromHistory: true });
      if (state.view === "folder-gallery" || state.view === "imagine-library") state.view = "gallery";
      const requestedFilter = normalizeGalleryFilter(button.dataset.workspaceMediaFilter || "all");
      state.filter = requestedFilter === state.filter ? "all" : requestedFilter;
      syncWorkspaceView();
      renderGallery();
      syncGalleryRouteAfterFilter(previousView);
    });
  });

  els.submitBtn.addEventListener("click", submit);
  els.savePromptBtn.addEventListener("click", () => savePrompt().catch((error) => toastError(error.message)));
  els.promptNewBtn?.addEventListener("click", () => {
    openPromptEditor(null, { create: true, mode: "note" });
  });
  els.refreshBtn.addEventListener("click", () => {
    loadState().catch((error) => toastError(error.message));
  });
  els.libraryFolderBtn?.addEventListener("click", () => {
    openMediaFolder().catch((error) => toastError(error.message));
  });
  els.setLibraryPathBtn?.addEventListener("click", () => {
    setLibraryFolder().catch((error) => showErrorPanel("Library folder failed", error.message));
  });
  els.accountButton?.addEventListener("click", () => {
    showAccountScreen(true, { pushHistory: true });
  });
  els.usagePageBtn?.addEventListener("click", async () => {
    if (state.generationProvider === "imagine") {
      try {
        const data = await api("/api/imagine/usage-page", {
          method: "POST",
          body: JSON.stringify({ anchor: browserWindowAnchor() }),
        });
        toast(data.fallback
          ? "Opened usage page. Chrome profile was not available."
          : "Opened Imagine usage page.");
      } catch (error) {
        toastError(error.message);
      }
      return;
    }
    const popupWidth = 560;
    const popupHeight = 760;
    const popupLeft = Math.max(0, Math.round((window.screen.availWidth - popupWidth) / 2));
    const popupTop = Math.max(0, Math.round((window.screen.availHeight - popupHeight) / 2));
    const popupFeatures = [
      "popup=yes",
      "toolbar=no",
      "location=no",
      "status=no",
      "menubar=no",
      "scrollbars=yes",
      "resizable=yes",
      `width=${popupWidth}`,
      `height=${popupHeight}`,
      `left=${popupLeft}`,
      `top=${popupTop}`,
    ].join(",");
    const page = window.open(
      "https://grok.com/?_s=usage",
      "grokUsagePage",
      popupFeatures,
    );
    if (page) {
      page.resizeTo?.(popupWidth, popupHeight);
      page.moveTo?.(popupLeft, popupTop);
      window.setTimeout(() => {
        page.resizeTo?.(popupWidth, popupHeight);
        page.moveTo?.(popupLeft, popupTop);
      }, 600);
      page.focus();
    } else {
      toast("Allow popups to open the usage page.");
    }
  });
  els.accountScreen?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") showAccountScreen(false);
  });
  els.registerAccountBtn?.addEventListener("click", () => registerAccount().catch((error) => showErrorPanel("Accounts failed", error.message)));
  els.imagineLoginBtn?.addEventListener("click", () => startImagineLogin().catch((error) => showErrorPanel("Imagine failed", error.message)));
  els.imagineCaptureBtn?.addEventListener("click", () => captureImagineLogin().catch((error) => showErrorPanel("Imagine failed", error.message)));
  els.imagineLogoutBtn?.addEventListener("click", () => clearImagineLogin().catch((error) => showErrorPanel("Imagine failed", error.message)));
  els.imagineAllViewBtn?.addEventListener("click", () => {
    const refresh = state.view === "imagine-library"
      && state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL
      && state.imaginePortfolioTypeFilter === IMAGINE_PORTFOLIO_TYPE_ALL;
    openImagineLibrary({ remoteView: IMAGINE_REMOTE_VIEW_ALL, portfolioType: IMAGINE_PORTFOLIO_TYPE_ALL, refresh });
  });
  els.imagineDiscoverViewBtn?.addEventListener("click", () => {
    const refresh = state.view === "imagine-library"
      && state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER
      && state.imagineDiscoverTypeFilter === IMAGINE_DISCOVER_TYPE_ALL;
    openImagineLibrary({ remoteView: IMAGINE_REMOTE_VIEW_DISCOVER, discoverType: IMAGINE_DISCOVER_TYPE_ALL, refresh });
  });
  els.imagineAllFilesViewBtn?.addEventListener("click", () => {
    const refresh = state.view === "imagine-library" && state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES;
    state.imagineAllFilesTypeFilter = IMAGINE_ALL_FILES_TYPE_ALL;
    openImagineLibrary({ remoteView: IMAGINE_REMOTE_VIEW_ALL_FILES, allFilesType: IMAGINE_ALL_FILES_TYPE_ALL, refresh });
  });
  document.querySelectorAll("[data-imagine-media-type]").forEach((button) => {
    button.addEventListener("click", () => {
      const requestedType = normalizeImagineMediaTypeFilter(button.dataset.imagineMediaType || IMAGINE_MEDIA_TYPE_ALL);
      const activeType = currentImagineMediaTypeFilter();
      const nextType = requestedType === activeType ? IMAGINE_MEDIA_TYPE_ALL : requestedType;
      if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_DISCOVER) {
        setImagineDiscoverTypeFilter(nextType);
        replaceImagineLibraryHistory();
        renderImagineLibrary();
        resetImagineLibraryScroll();
        if (!state.imagineRemoteLoadedOnce && !state.imagineRemoteBusy) {
          loadImagineRemoteLibrary({ reset: true }).catch((error) => showErrorPanel("Imagine failed", error.message));
          return;
        }
        fillImagineDiscoverTypeIfNeeded(nextType).catch((error) => console.warn(error));
        return;
      }
      if (state.imagineRemoteView === IMAGINE_REMOTE_VIEW_ALL_FILES) {
        setImagineAllFilesTypeFilter(nextType);
        replaceImagineLibraryHistory();
        renderImagineLibrary();
        resetImagineLibraryScroll();
        return;
      }
      setImaginePortfolioTypeFilter(nextType);
      replaceImagineLibraryHistory();
      renderImagineLibrary();
      resetImagineLibraryScroll();
      if (!state.imagineRemoteLoadedOnce && !state.imagineRemoteBusy) {
        loadImagineRemoteLibrary({ reset: true }).catch((error) => showErrorPanel("Imagine failed", error.message));
        return;
      }
      fillImaginePortfolioTypeIfNeeded(nextType).catch((error) => console.warn(error));
    });
  });
  els.imagineImportBtn?.addEventListener("click", importSelectedImagineItems);
  els.downloadSelectedBtn.addEventListener("click", downloadSelectedItems);
  els.moveToGalleryBtn?.addEventListener("click", openMoveToGalleryDialog);
  els.deleteSelectedBtn.addEventListener("click", () => deleteSelectedItems().catch((error) => toastError(error.message)));
  els.selectionDownloadBtn?.addEventListener("click", downloadSelectedItems);
  els.selectionDeleteBtn?.addEventListener("click", () => deleteSelectedItems().catch((error) => toastError(error.message)));
  els.selectionClearBtn?.addEventListener("click", () => {
    state.selectedItems.clear();
    renderGallery();
  });
  els.librarySelectionClearBtn?.addEventListener("click", () => {
    state.selectedItems.clear();
    renderGallery();
  });
  els.modelToggleButtons.forEach((button) => {
    button.addEventListener("click", () => setVideoModel(button.dataset.videoModel || ""));
  });
  els.videoModelInput?.addEventListener("change", () => setVideoModel(els.videoModelInput.value));
  setVideoModel(state.videoModel);
  els.imageModelInput?.addEventListener("change", () => setImageModel(els.imageModelInput.value));
  setImageModel(state.imageModel);
  els.closeErrorBtn.addEventListener("click", hideErrorPanel);
  els.copyErrorBtn.addEventListener("click", () => {
    copyText(state.lastErrorText || els.errorBody.textContent || "")
      .catch((error) => toastError(error.message));
  });
  const activateSearchView = () => {
    if (state.accountScreenVisible) showAccountScreen(false);
    if (state.view === "detail") closeDetail();
    if (state.view === "folder-gallery") state.view = "gallery";
    syncWorkspaceView();
    renderGallery();
  };
  els.searchInput.addEventListener("focus", activateSearchView);
  els.searchInput.addEventListener("input", activateSearchView);
  els.sidebarSearchLabel?.addEventListener("click", (event) => {
    if (state.accountScreenVisible) showAccountScreen(false);
    if (!state.sidebarCollapsed) return;
    event.preventDefault();
    setSidebarCollapsed(false);
    window.setTimeout(() => els.searchInput.focus(), 220);
  });
  ["pointerdown", "mousedown", "touchstart"].forEach((eventName) => {
    els.promptInput.addEventListener(eventName, beginDetailExtendComposerGesture, { capture: true });
  });
  ["pointerup", "pointercancel", "mouseup", "touchend", "touchcancel"].forEach((eventName) => {
    document.addEventListener(eventName, endDetailExtendComposerGesture, { capture: true });
  });
  els.promptInput.addEventListener("input", () => {
    markDetailExtendComposerIntent();
    autoSizePromptInput();
    ensureDetailExtendComposerState();
  });
  els.promptInput.addEventListener("focus", () => {
    markDetailExtendComposerIntent();
    setPromptExpanded(true);
    ensureDetailExtendComposerState();
  });
  els.promptInput.addEventListener("click", () => {
    markDetailExtendComposerIntent();
    setPromptExpanded(true);
    ensureDetailExtendComposerState();
  });
  els.composerAttachBtn?.addEventListener("click", () => {
    toggleAttachmentTray();
  });
  document.addEventListener("click", (event) => {
    if (!state.promptExpanded || !(event.target instanceof Element)) return;
    if (event.target === els.promptInput) return;
    setPromptExpanded(false);
  });
  document.addEventListener("click", (event) => {
    if (!state.attachmentTrayOpen || !(event.target instanceof Element)) return;
    if (event.target.closest(".lab-composer")) return;
    toggleAttachmentTray(false);
  });
  document.addEventListener("click", handleDetailExtendBlankClick);
  ["dragenter", "dragover", "drop"].forEach((eventName) => {
    els.promptInput.addEventListener(eventName, blockPromptDrop);
  });
  els.sourceVideoSelect.addEventListener("change", () => {
    state.selectedVideoId = els.sourceVideoSelect.value;
  });

  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element ? event.target.closest(".image-preview-trigger") : null;
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();
    openImagePreview(trigger.dataset.previewSrc, trigger.dataset.previewTitle);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeImagePreview();
      closePromptEditor();
      closeLibraryFolderDialog();
      closeMoveToGalleryDialog();
    }
  });

  els.imageFiles.addEventListener("change", () => {
    addComposerImageFiles(els.imageFiles.files).catch((error) => showErrorPanel("Image failed", error.message));
    els.imageFiles.value = "";
  });
  els.imageSourceDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    els.imageSourceDrop.classList.add("drag-over");
  });
  els.imageSourceDrop.addEventListener("dragleave", () => {
    els.imageSourceDrop.classList.remove("drag-over");
  });
  els.imageSourceDrop.addEventListener("drop", (event) => {
    handleEditImageDrop(event).catch((error) => showErrorPanel("Image failed", error.message));
  });
  els.startImageDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    els.startImageDrop.classList.add("drag-over");
  });
  els.startImageDrop.addEventListener("dragleave", () => {
    els.startImageDrop.classList.remove("drag-over");
  });
  els.startImageDrop.addEventListener("drop", (event) => {
    handleStartImageDrop(event).catch((error) => toastError(error.message));
  });
  els.startImageFile.addEventListener("change", () => {
    const file = els.startImageFile.files?.[0];
    if (file) {
      setStartImageFromFile(file).catch((error) => toastError(error.message));
    } else {
      clearStartImage();
    }
  });
  els.referenceImageFiles.addEventListener("change", () => {
    addReferenceImageFiles(els.referenceImageFiles.files).catch((error) => showErrorPanel("Image failed", error.message));
  });
  els.referenceImageDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    els.referenceImageDrop.classList.add("drag-over");
  });
  els.referenceImageDrop.addEventListener("dragleave", () => {
    els.referenceImageDrop.classList.remove("drag-over");
  });
  els.referenceImageDrop.addEventListener("drop", (event) => {
    handleReferenceImageDrop(event).catch((error) => showErrorPanel("Image failed", error.message));
  });
  els.sourceVideoDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    els.sourceVideoDrop.classList.add("drag-over");
  });
  els.sourceVideoDrop.addEventListener("dragleave", () => {
    els.sourceVideoDrop.classList.remove("drag-over");
  });
  els.sourceVideoDrop.addEventListener("drop", handleSourceVideoDrop);
  els.sourceVideoFile.addEventListener("change", () => {
    const file = els.sourceVideoFile.files?.[0];
    if (file) {
      setSourceVideoFromFile(file);
    } else {
      clearSourceVideo();
    }
  });
  window.addEventListener("pagehide", sendShutdownSignal);
  window.addEventListener("beforeunload", sendShutdownSignal);
}

function schedulePostJobRefresh(jobs) {
  const key = (jobs || [])
    .map((job) => String(job?.id || ""))
    .filter(Boolean)
    .sort()
    .join("|");
  if (!key || state.postJobRefreshTimers.has(key)) return;
  const timer = window.setTimeout(() => {
    state.postJobRefreshTimers.delete(key);
    loadState().catch((error) => console.warn(error));
  }, 10000);
  state.postJobRefreshTimers.set(key, timer);
}

async function pollJobs() {
  try {
    const data = await api("/api/jobs");
    state.jobs = data.jobs || [];
    const disposableJobs = state.jobs.filter((job) => ["done", "cancelled"].includes(job.status));
    const newlyDoneJobs = [];
    const newlyFailedJobs = [];
    for (const job of state.jobs) {
      if (job.status === "failed" && !state.notifiedJobs.has(job.id)) {
        state.notifiedJobs.add(job.id);
        newlyFailedJobs.push(job);
        if (state.view === "detail" && state.detailSelectedJobId === job.id && job.prompt) {
          els.promptInput.value = job.prompt;
          autoSizePromptInput();
        }
        if (isModerationError(job.error)) {
          toastError(moderationToastMessage());
        } else if (!isCreditLimitError(job.error)) {
          showErrorPanel("Job failed", job.error || "Unknown error");
        }
      }
      if (job.status === "done" && !state.notifiedJobs.has(job.id)) {
        state.notifiedJobs.add(job.id);
        newlyDoneJobs.push(job);
        const doneItem = job.item || (Array.isArray(job.items) ? job.items[0] : null);
        const doneFolderId = String(jobContext(job).gallery_folder_id || "");
        if (state.view === "detail" && doneItem?.id && doneFolderId === state.workspaceFolderId) {
          state.detailItemId = doneItem.id;
          replaceDetailHistory(doneItem.id);
          state.detailSelectedSourceUrl = "";
          state.detailSelectedJobId = "";
          state.detailExtend = false;
          state.detailExtendStart = 0;
        }
      }
    }
    if (disposableJobs.length) {
      state.jobs = state.jobs.filter((job) => !["done", "cancelled"].includes(job.status));
    }
    renderJobs();
    updateGalleryJobOverlays();
    if (state.view === "detail" && detailVisualJobs().length) updateDetailJobOverlays();
    if (disposableJobs.length) {
      await Promise.all(disposableJobs.map((job) => (
        api(`/api/jobs/${job.id}/dismiss`, { method: "POST", body: "{}" }).catch((error) => console.warn(error))
      )));
    }
    if (newlyDoneJobs.length || newlyFailedJobs.length) {
      await loadState();
      schedulePostJobRefresh([...newlyDoneJobs, ...newlyFailedJobs]);
    }
  } catch (error) {
    console.warn(error);
  } finally {
    setTimeout(pollJobs, 3000);
  }
}

function sendShutdownSignal() {
  if (sessionStorage.getItem(INTERNAL_EDITOR_NAV_KEY) === "1") return;
  if (state.shutdownSent) return;
  state.shutdownSent = true;
  const body = JSON.stringify({ event: "tab-close", at: new Date().toISOString() });
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/shutdown", new Blob([body], { type: "application/json" }));
      return;
    }
  } catch (error) {
    console.warn(error);
  }
  fetch("/api/shutdown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {});
}

function heartbeat() {
  fetch("/api/heartbeat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    keepalive: true,
  }).catch(() => {});
}

initializeBrowserHistory();
bindEvents();
window.addEventListener("message", (event) => {
  handleImageEditorMessage(event).catch((error) => toastError(error.message));
});
window.addEventListener("pageshow", () => {
  consumeImageEditorReturn().catch((error) => toastError(error.message));
});
setMode("image");
autoSizePromptInput();
loadState().catch((error) => toastError(error.message));
pollJobs();
heartbeat();
setInterval(heartbeat, 3000);
