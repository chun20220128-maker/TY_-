let webProjectDirty=false,webEnding=false;
const webOriginalSave=save;save=function(){webOriginalSave();$('saveStatus').textContent='專案暫存中，請匯出備份保存'};
const webOriginalStatus=historyDatabaseStatus;historyDatabaseStatus=function(message){webOriginalStatus(message);$('saveStatus').textContent=historyDatabase.error?'共用單價尚未寫入；專案請先匯出備份':historyDatabase.ready?'共用單價已同步；專案請自行匯出備份':'正在連線共用單價…'};
// A project backup must never silently overwrite the company's reference library.
const webOriginalInstall=installProject;installProject=function(candidate,options={}){candidate=structuredClone(candidate);candidate.history=structuredClone(state.history);webOriginalInstall(candidate,{...options,keepHistory:false});webProjectDirty=true;$('saveStatus').textContent='專案已載入畫面，請自行匯出備份保存'};
document.addEventListener('input',event=>{if(event.target.id!=='historyFile'&&event.target.closest('.section,.project'))webProjectDirty=true});
parent.addEventListener('beforeunload',event=>{if(webProjectDirty&&!webEnding){event.preventDefault();event.returnValue=''}});
const webExit=document.createElement('button');webExit.textContent='結束作業';webExit.id='webExit';webExit.style.marginTop='12px';document.querySelector('aside').appendChild(webExit);
const exitDialog=document.createElement('dialog');exitDialog.id='webExitDialog';exitDialog.style.width='590px';exitDialog.innerHTML='<h2>結束前，是否先匯出專案備份？</h2><p>結束後，本次專案作業將不保留。歷史單價已由公司共用資料庫保存。</p><div class="toolbar"><button id="webBackupExit" class="requirements-button">先匯出備份，再結束</button><button id="webDiscardExit">不備份，結束作業</button><button id="webCancelExit">取消</button><button id="webFinishExit" class="primary" hidden>已保存備份，結束作業</button></div><p id="webExitStatus" role="status"></p>';document.body.appendChild(exitDialog);
webExit.onclick=()=>{$('webFinishExit').hidden=true;$('webExitStatus').textContent='';exitDialog.showModal()};$('webCancelExit').onclick=()=>exitDialog.close();
async function finishWebSession(){try{clearTimeout(historyDatabase.timer);for(let n=0;historyDatabase.busy&&n<100;n++)await new Promise(r=>setTimeout(r,50));await flushHistoryDatabase();if(!historyDatabase.ready||historyDatabase.error||historyDatabaseChanges().length)throw Error('共用單價尚未完成寫入，作業保持開啟，請確認連線或先備份。');webEnding=true;webProjectDirty=false;parent.location.reload()}catch(error){$('webExitStatus').textContent=error.message}}
$('webDiscardExit').onclick=finishWebSession;$('webFinishExit').onclick=finishWebSession;$('webBackupExit').onclick=async()=>{try{if(await writeCompleteBackup()){webProjectDirty=false;await finishWebSession()}else{$('webFinishExit').hidden=false;$('webExitStatus').textContent='備份已開始下載，確認保存後再按「已保存備份，結束作業」。'}}catch(error){$('webExitStatus').textContent=error.name==='AbortError'?'已取消備份，作業保持開啟。':'備份未完成：'+error.message}};
const conflict=document.createElement('dialog');conflict.id='sharedHistoryConflict';conflict.innerHTML='<h2>共用單價已由其他工程師更新</h2><p>本次歷史單價尚未寫入。請重新載入共用單價，核對後再選取 CSV 匯入；目前專案會保留在畫面中。</p><button id="reloadSharedHistory" class="primary">重新載入共用單價</button> <button id="cancelSharedReload">稍後處理</button><p id="sharedConflictStatus"></p>';document.body.appendChild(conflict);
window.showSharedHistoryConflict=()=>{if(!conflict.open)conflict.showModal()};$('cancelSharedReload').onclick=()=>conflict.close();$('reloadSharedHistory').onclick=async()=>{try{const response=await fetch('/api/history');if(!response.ok)throw Error('無法連線，請稍後再試');const remote=await response.json();state.history=remote.records;historyDatabase.revision=remote.revision;historyDatabase.baseline=new Map(remote.records.map(h=>[historyIdentity(h),historyKey(h)]));historyDatabase.ready=true;historyDatabase.error='';localStorage.setItem('geotech-history-outbox-v1','[]');render();renderHistory();save();conflict.close()}catch(error){$('sharedConflictStatus').textContent=error.message}};
document.addEventListener('click',event=>{if(event.target.closest('#viewHistory')&&!historyDatabase.busy&&!historyDatabaseChanges().length){historyDatabase.error='';connectHistoryDatabase()}});
$('saveStatus').textContent='專案暫存中；歷史單價連線後全公司共用';

// Company web edition: reference library is read-only. Desktop source is unchanged.
for(const id of ['importHistory','exportHistory','template','historyFile'])$(id)?.remove();
for(const p of document.querySelectorAll('#estimate .sub'))if(p.textContent.includes('可持續匯入'))p.textContent='公司共用歷史契約單價，僅供查閱及建議單價參考。';
for(const p of document.querySelectorAll('#historyDialog .sub'))for(const n of p.childNodes)if(n.nodeType===3)n.textContent=n.textContent.replace('匯出 CSV 使用目前篩選與排序結果。','');
backupContents=function(){const data=structuredClone(state);data.history=[];return JSON.stringify({format:'geotech-backup',backupVersion:2,exportedAt:new Date().toISOString(),sections:['規劃','估價','契約','請款'],data},null,2)};
// Disable file and programmatic import paths as well as the UI.
queueHistoryDatabaseSave=function(){};
flushHistoryDatabase=async function(){};

const webLogout=document.createElement('button');webLogout.id='webLogout';webLogout.textContent='登出';document.querySelector('aside').appendChild(webLogout);webLogout.onclick=async()=>{if(webProjectDirty&&!confirm('尚未備份的專案將不保留。請先取消並匯出備份，或按確定登出。'))return;try{const response=await fetch('/api/logout',{method:'POST'});if(!response.ok)throw Error('登出失敗，請稍後重試。');webEnding=true;webProjectDirty=false;parent.location.reload()}catch(e){toast(e.message)}};
