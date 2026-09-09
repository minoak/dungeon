// 실행: python art/sprites-v4/serve-preview.py, 별도 터미널에서 node art/sprites-v4/verify-browser.mjs
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const {chromium}=await import('playwright').catch(()=>import(pathToFileURL(path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'))));
const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'msedge'}:{})});
const origin=process.env.WL_PREVIEW_URL || 'http://127.0.0.1:8766';
const errors=[];
try {
  const page=await browser.newPage({viewport:{width:1280,height:1080}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/art/sprites-v4/');
  await page.waitForFunction(()=>document.querySelector('#status').textContent==='세 외형 준비 완료');
  const summary=await page.evaluate(()=>{
    let frames=0;
    for(const preset of WLSprites.illustrations())for(const hair of WLSprites.hairstyles({sprite:preset.id}))for(const dir of WLSprites.DIRS)for(let p=-1;p<4;p++){
      const c=WLSprites.cell({sprite:preset.id,hairstyle:hair.id},dir,p),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let count=0,bottom=0,left=c.width,right=0;
      for(let i=0;i<d.length;i+=4){
        if(d[i+3]!==0 && d[i+3]!==255)throw new Error('반투명 경계');
        if(!d[i+3])continue;
        count++;const x=(i/4)%c.width,y=Math.floor(i/4/c.width);
        left=Math.min(left,x);right=Math.max(right,x);bottom=Math.max(bottom,y);
        if(d[i]>180 && d[i+2]>180 && d[i+1]<40)throw new Error('분홍 배경 잔여');
      }
      if(count<1000 || left<2 || right>93 || bottom!==91)throw new Error('빈 프레임·잘림·발 위치 불일치');
      frames++;
    }
    const old=WLSprites.cell({head:'F3',body:'B2',colors:{hair:'#352c2c'}},'back',2);
    if(old.width!==16)throw new Error('기존 파츠 호환 실패');
    return {frames,oldWidth:old.width};
  });
  assert.equal(summary.frames,220);
  await page.locator('#play').click();
  // 같은 프레임에서 머리만 선택해 캔버스 캐시가 서로 섞이지 않는지 확인한다.
  for(let i=0;i<3;i++){
    const select=page.locator(`[data-hair="${i}"]`),images=[];
    const options=await select.locator('option').evaluateAll(es=>es.map(e=>e.value));
    assert.equal(options.length,i===0?5:3);
    for(const value of options){
      await select.selectOption(value);
      images.push(await page.locator(`.stage [data-art="${i}"]`).evaluate(c=>c.toDataURL()));
    }
    assert.equal(new Set(images).size,options.length);
  }
  for(const dir of ['front','right','back','left']){
    await page.locator(`[data-dir=${dir}]`).click();
    assert.equal(await page.locator(`[data-dir=${dir}]`).getAttribute('aria-pressed'),'true');
    for(let i=0;i<4;i++){await page.locator('#frame').fill(String(i));assert.equal(await page.locator('#number').textContent(),`${i+1} / 4`);}
  }
  await page.locator('[data-dir=front]').click();await page.locator('#motion').click();
  await page.screenshot({path:path.join(here,'hairstyles/gallery-preview.png'),fullPage:true});
  await page.locator('#cards').screenshot({path:path.join(here,'hairstyles/selection-preview.png')});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.setViewportSize({width:1280,height:1080});
  await page.goto(origin+'/launcher/');await page.locator('#bNew').click();
  await page.waitForSelector('[data-art]');
  assert.deepEqual(await page.locator('[data-art]').evaluateAll(es=>es.map(e=>e.value)),['sd-warrior','sd-rogue','sd-archer']);
  assert.equal(await page.locator('.lookPrev').first().getAttribute('width'),'96');
  const first=page.locator('.card').first();
  await first.locator('[data-art]').selectOption('');
  assert.equal(await first.locator('.lookParts').isVisible(),true);
  assert.equal(await first.locator('.lookPrev').getAttribute('width'),'16');
  await first.locator('[data-lk=head] label').nth(6).click();
  await first.locator('[data-art]').selectOption('sd-warrior');
  assert.equal(await first.locator('.lookParts').isVisible(),false);
  assert.equal(await first.locator('[data-hairstyle] option').count(),5);
  await first.locator('[data-hairstyle]').selectOption('parted');
  await first.locator('[data-art]').selectOption('sd-archer');
  assert.equal(await first.locator('[data-hairstyle]').inputValue(),'default');
  assert.equal(await first.locator('[data-hairstyle] option[value=parted]').count(),0);
  await first.locator('[data-art]').selectOption('sd-warrior');
  for(let i=0;i<3;i++){
    const card=page.locator('.card').nth(i);
    await card.locator('[data-hairstyle]').selectOption(['twintails','ponytail','braid'][i]);
    await card.locator('[data-k=name]').fill('도트검증'+(i+1));
    await card.locator('[data-k=persona]').fill('신중하게 주변을 살피는 모험가.');
  }
  await page.screenshot({path:path.join(here,'hairstyles/launcher-preview.png'),fullPage:true});
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/party') && r.request().method()==='POST');
  await page.locator('#bNext').click();const response=await saved;assert.equal(response.status(),200);
  assert.deepEqual(response.request().postDataJSON().slots.map(s=>s.look.hairstyle),['twintails','ponytail','braid']);
  await page.goto(origin+'/viewer/?run=art/sprites-v4/demo-hairstyles.jsonl');
  await page.waitForFunction(()=>document.querySelectorAll('.face.sd-face').length===3);
  assert.equal(await page.locator('#err').textContent(),'');
  await page.locator('#mapScale').selectOption('close');
  assert.deepEqual(await page.evaluate(()=>Object.values(looks).map(l=>l.hairstyle)),['long','braid','ponytail']);
  await page.screenshot({path:path.join(here,'hairstyles/viewer-preview.png'),fullPage:true});
  await page.locator('#bPlay').click();
  await page.waitForFunction(()=>document.querySelector('#slider').value!=='0');
  await page.locator('#bPlay').click();
  const degraded=await browser.newPage();
  degraded.on('pageerror',e=>errors.push(e.message));
  await degraded.route('**/sd/warrior.png',r=>r.abort());
  await degraded.goto(origin+'/art/sprites-v4/');
  await degraded.waitForFunction(()=>window.WLSprites?.ready && document.querySelector('#status').textContent.includes('불러오지'));
  assert.deepEqual(await degraded.evaluate(()=>[
    WLSprites.cell({sprite:'sd-warrior',head:'M1',body:'B1'},'front',-1).width,
    WLSprites.cell({sprite:'sd-archer'},'front',-1).width]),[16,96]);
  const missingHair=await browser.newPage();
  missingHair.on('pageerror',e=>errors.push(e.message));
  await missingHair.route('**/sd/warrior-parted.png',r=>r.abort());
  await missingHair.goto(origin+'/art/sprites-v4/');
  await missingHair.waitForFunction(()=>document.querySelector('#status').textContent==='세 외형 준비 완료');
  assert.equal(await missingHair.evaluate(()=>
    WLSprites.cell({sprite:'sd-warrior',hairstyle:'parted'},'front',0).toDataURL()===
    WLSprites.cell({sprite:'sd-warrior'},'front',0).toDataURL()),true);
  assert.deepEqual(errors,[]);
  console.log('PASS: 220프레임 알파·잘림·발 정렬, 11종 머리 실제 표시/캐시 분리, 방향/프레임 조작, 모바일 너비, 론처 머리 전환/저장, 실제 뷰어/재생, PNG·머리 파일 실패 폴백, JS 오류 없음');
} finally {await browser.close();}
