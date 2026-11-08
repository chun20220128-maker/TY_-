// Project work lives only in host memory; historical prices persist independently.
let desktopStopped=false;
const desktopBrowserSave=save;
const desktopInitialHistory=new Map(state.history.map(h=>[historyIdentity(h),historyKey(h)]));
function desktopPendingChanges(){if(historyDatabase.ready)return historyDatabaseChanges();const pending=new Map((state.desktopPendingHistory||[]).map(h=>[historyIdentity(h),h]));for(const h of state.history)if(desktopInitialHistory.get(historyIdentity(h))!==historyKey(h))pending.set(historyIdentity(h),h);return [...pending.values()]}
if(!window.desktopInitialProject){state.zones=[];state.project.district='';state.items=defs.map(([id,name,unit])=>({id,name,unit,adopted:0,rate:120,status:'待確認',reason:'',qty:id==='report'?0:1}));render()}
function desktopDiskSave(){const request=new XMLHttpRequest();request.open('POST','/api/project',false);request.setRequestHeader('Content-Type','application/json');const snapshot={...state,desktopPage:page,desktopView:view,desktopPlanEditing:planEditing,desktopScroll:window.scrollY,desktopPendingHistory:desktopPendingChanges()};request.send(JSON.stringify(snapshot));if(request.status!==200)throw Error('背景作業暫存失敗，請先匯出備份並確認本機服務是否正常');$('saveStatus').textContent='本次作業暫存中（結束後不保留） '+new Date().toLocaleTimeString('zh-TW')}
save=function(){if(desktopStopped)return;desktopBrowserSave();try{desktopDiskSave()}catch(error){$('saveStatus').textContent='背景暫存失敗';toast(error.message)}};
const desktopHistoryStatus=historyDatabaseStatus;
historyDatabaseStatus=function(message){if(desktopStopped)return;desktopHistoryStatus(message);if(historyDatabase.error){$('saveStatus').textContent='本機歷史單價資料庫未就緒';toast('本機歷史單價資料庫尚未寫入，請勿移除 data 資料夾，並確認磁碟空間。')}else if(historyDatabase.ready){try{desktopDiskSave()}catch(error){$('saveStatus').textContent='背景暫存失敗';toast(error.message)}}};
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')save()});
window.addEventListener('pagehide',()=>{try{navigator.sendBeacon('/api/project',new Blob([JSON.stringify({...state,desktopPage:page,desktopView:view,desktopPlanEditing:planEditing,desktopScroll:window.scrollY,desktopPendingHistory:desktopPendingChanges()})],{type:'application/json'}))}catch{}});
save();

const desktopQuit=document.createElement('button');desktopQuit.textContent='結束程式';desktopQuit.id='desktopQuit';desktopQuit.style.cssText='margin-top:12px';document.querySelector('aside').appendChild(desktopQuit);
const desktopExitDialog=document.createElement('dialog');desktopExitDialog.id='desktopExitDialog';desktopExitDialog.style.width='590px';desktopExitDialog.innerHTML=`<h2>結束前，是否先匯出專案備份？</h2><p>結束後，本次專案作業將不保留。需要接續作業時，請先匯出備份。</p><p class="sub">歷史單價會自動保存在本機，不受結束程式影響。</p><div class="toolbar" style="margin-top:20px;flex-wrap:wrap"><button id="desktopBackupExit" class="requirements-button">先匯出備份，再結束</button><button id="desktopDiscardExit">不備份，結束程式</button><button id="desktopCancelExit">取消</button><button id="desktopFinishExit" class="primary" hidden>已保存備份，結束程式</button></div><p id="desktopExitStatus" role="status"></p>`;document.body.appendChild(desktopExitDialog);
async function desktopCancelExit(){try{await fetch('/api/desktop-cancel-stop',{method:'POST'})}catch{}desktopExitDialog.close();desktopQuit.disabled=false}
async function desktopFinishExit(){
 const buttons=desktopExitDialog.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);
 try{desktopDiskSave();clearTimeout(historyDatabase.timer);for(let attempt=0;historyDatabase.busy&&attempt<100;attempt++)await new Promise(resolve=>setTimeout(resolve,50));await flushHistoryDatabase();if(!historyDatabase.ready||historyDatabase.busy||historyDatabase.error||historyDatabaseChanges().length)throw Error('歷史單價尚未完成寫入，程式保持開啟，請確認儲存狀態');const response=await fetch('/api/desktop-stop',{method:'POST'});if(!response.ok)throw Error('結束本機服務失敗');desktopStopped=true;clearInterval(desktopSessionPoll);clearTimeout(window.desktopScrollTimer);document.body.innerHTML='<main style="margin:40px;font-family:Microsoft JhengHei,sans-serif"><h1>鑽探工作台已結束</h1><p>歷史單價已儲存。本次專案未自動保存；已匯出的備份檔不受影響。</p></main>';window.close()}
 catch(error){try{await fetch('/api/desktop-cancel-stop',{method:'POST'})}catch{}$('desktopExitStatus').textContent=error.message;buttons.forEach(b=>b.disabled=false)}
}
desktopQuit.onclick=()=>{if(desktopExitDialog.open)return;desktopQuit.disabled=true;$('desktopExitStatus').textContent='';$('desktopFinishExit').hidden=true;desktopExitDialog.querySelectorAll('button').forEach(b=>b.disabled=false);desktopExitDialog.showModal()};
$('desktopDiscardExit').onclick=desktopFinishExit;
$('desktopCancelExit').onclick=desktopCancelExit;
desktopExitDialog.addEventListener('cancel',event=>{event.preventDefault();desktopCancelExit()});
$('desktopFinishExit').onclick=desktopFinishExit;
$('desktopBackupExit').onclick=async()=>{const button=$('desktopBackupExit');button.disabled=true;try{if(await writeCompleteBackup())await desktopFinishExit();else{$('desktopExitStatus').textContent='備份已開始下載，請確認檔案已保存，再按「已保存備份，結束程式」。';$('desktopFinishExit').hidden=false}}catch(error){$('desktopExitStatus').textContent=error.name==='AbortError'?'已取消備份，程式保持開啟。':'備份未完成，程式保持開啟：'+error.message}finally{button.disabled=false}};
// Backup restore and new-project use installProject directly rather than save().
const desktopInstallProject=installProject;
installProject=function(...args){desktopInstallProject(...args);desktopDiskSave()};

// A warm reopen restores the active page; a new host has no prior project injected.
if(window.desktopInitialProject){planEditing=!!state.desktopPlanEditing;if(['both','design','owner'].includes(state.desktopView))view=state.desktopView;render()}
if(state.desktopPage&&document.querySelector('[data-nav="'+state.desktopPage+'"]')){document.querySelector('[data-nav="'+state.desktopPage+'"]').click();requestAnimationFrame(()=>window.scrollTo(0,state.desktopScroll||0))}
document.addEventListener('click',event=>{if(event.target.closest('[data-nav]'))save()});
window.addEventListener('scroll',()=>{clearTimeout(window.desktopScrollTimer);window.desktopScrollTimer=setTimeout(save,250)},{passive:true});
const desktopSessionPoll=setInterval(async()=>{try{const response=await fetch('/api/desktop-session',{cache:'no-store'});if(response.ok&&(await response.json()).quit&&!desktopQuit.disabled)desktopQuit.click()}catch{}},1000);
