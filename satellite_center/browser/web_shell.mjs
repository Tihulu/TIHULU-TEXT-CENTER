/* Static web/PWA navigation and compact EN(default)/TR/DE shell translations.
 * Preserve native RTL-SDR application and browser's existing feature modules.
 */
export const SECTIONS=Object.freeze([
  {id:"receiver",href:"./index.html",label:"receiver"},
  {id:"images",href:"./reception.html",label:"images"},
  {id:"earth",href:"./index.html#satellite-tracking-maps",label:"earth"},
  {id:"analysis",href:"./index.html#iq-analysis",label:"analysis"}
]);
export const UI_TEXT=Object.freeze({
  en:{
    receiver:"Receiver & Planner",images:"Satellite Images & Data",earth:"Earth / Sky",
    analysis:"Signal Analysis",language:"Interface language",webEdition:"Chromium WebUSB Edition",
    statusIdle:"No receiver acquired. Maps and planning need no radio.",
    stepTitle:"Auto-Capture & Decode · three steps",step1:"1 · Auto Schedule & Capture",
    step2:"2 · Analyze Recordings",step3:"3 · Extract Results",
    connect:"Choose RTL-SDR (WebUSB)",disconnect:"Disconnect & release",
    stop:"Stop & release",capture:"Start real USB capture",
    noGuarantee:"Browser USB capture requires a visible, awake Chromium tab. No silent background RF.",
    assetsOk:"Web app shell ready · SDR remains off until permission is granted."
  },
  tr:{
    receiver:"Alıcı ve Planlayıcı",images:"Uydu Görselleri ve Veriler",earth:"Dünya / Gökyüzü",
    analysis:"Sinyal Analizi",language:"Arayüz dili",webEdition:"Chromium WebUSB Sürümü",
    statusIdle:"Alıcı kullanılmıyor. Haritalar ve planlama radyo gerektirmez.",
    stepTitle:"Otomatik Kayıt ve Çözümleme · üç adım",
    step1:"1 · Otomatik Planla ve Kaydet",step2:"2 · Kayıtları Analiz Et",
    step3:"3 · Sonuçları Çıkar",connect:"RTL-SDR Seç (WebUSB)",
    disconnect:"Bağlantıyı kes ve serbest bırak",stop:"Durdur ve serbest bırak",
    capture:"Gerçek USB kaydını başlat",
    noGuarantee:"WebUSB kaydı için görünür ve uyanık bir Chromium sekmesi gerekir. Gizli arka plan kaydı yok.",
    assetsOk:"Web uygulaması hazır · izin verilene kadar SDR kapalıdır."
  },
  de:{
    receiver:"Empfänger & Planung",images:"Satellitenbilder & Daten",earth:"Erde / Himmel",
    analysis:"Signalanalyse",language:"Oberflächensprache",webEdition:"Chromium-WebUSB-Version",
    statusIdle:"Kein Empfänger belegt. Karten und Planung benötigen kein Funkgerät.",
    stepTitle:"Auto-Aufnahme & Dekodierung · drei Schritte",
    step1:"1 · Automatisch planen & aufnehmen",step2:"2 · Aufnahmen analysieren",
    step3:"3 · Ergebnisse extrahieren",connect:"RTL-SDR auswählen (WebUSB)",
    disconnect:"Trennen & freigeben",stop:"Stoppen & freigeben",
    capture:"Echte USB-Aufnahme starten",
    noGuarantee:"WebUSB benötigt einen sichtbaren, aktiven Chromium-Tab. Kein heimlicher Hintergrundempfang.",
    assetsOk:"Web-App bereit · SDR bleibt ohne Genehmigung ausgeschaltet."
  }
});
export function supportedLocale(locale){
  return Object.prototype.hasOwnProperty.call(UI_TEXT,locale)?locale:"en";
}
export function activeSection(pathname,hash=""){
  const last=String(pathname||"").split("/").pop();
  if(last==="reception.html")return "images";
  if(hash==="#satellite-tracking-maps")return "earth";
  if(hash==="#iq-analysis")return "analysis";
  return "receiver";
}
export function sectionHref(id){
  return SECTIONS.find(s=>s.id===id)?.href??SECTIONS[0].href;
}
export function applyShell(doc,win,{storage=win?.localStorage}={}){
  const readPref=()=>{try{return storage?.getItem("tihulu-satellite-ui-language")}catch{return null}};
  const writePref=value=>{try{storage?.setItem("tihulu-satellite-ui-language",value)}catch{}};
  const select=doc.getElementById("ui-language");
  const current=()=>activeSection(win?.location?.pathname,win?.location?.hash);
  const paint=locale=>{
    const language=supportedLocale(locale);
    doc.documentElement.lang=language;
    if(select)select.value=language;
    const labels=UI_TEXT[language];
    for(const element of doc.querySelectorAll("[data-shell-text]")){
      const key=element.getAttribute("data-shell-text");
      if(Object.prototype.hasOwnProperty.call(labels,key))element.textContent=labels[key];
    }
    for(const link of doc.querySelectorAll("a[data-shell-section]")){
      const id=link.getAttribute("data-shell-section");
      if(id===current()){link.setAttribute("aria-current","page");link.classList.add("active");}
      else{link.removeAttribute("aria-current");link.classList.remove("active");}
    }
    return language;
  };
  const initial=supportedLocale(readPref()||"en");
  paint(initial);
  select?.addEventListener("change",()=>{const lang=paint(select.value);writePref(lang)});
  win?.addEventListener?.("hashchange",()=>paint(select?.value||initial));
  return {paint,initial,active:current()};
}
