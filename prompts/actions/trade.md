# 사고팔기 — 말 · trade

<!-- p0.5.29 사고팔기(buy · sell)의 말. 조합형 관측과 직전 결과 문장에 들어간다(메뉴형의 가게 말은 따로다).
     p0.5.30: buy 가 상품이 아닌 대상에 닿았을 때의 결과 문장(buy_shop · buy_other · good).
     · 칸 이름(백틱 안)은 엔진이 읽는 열쇠라 바꾸지 않는다. 칸마다 한 줄.
     · 중괄호는 엔진이 채우는 자리다 — 칸마다 쓸 수 있는 자리가 정해져 있다(줄표 뒤 설명). 그 밖의 자리를 쓰면 게임이 뜨지 않는다.
       {buy}·{sell} = 동사 세트에서 그 처리기를 쓰는 동사 이름 · {verb} = 그때 고른 동사 · {shop} = 가게 이름 · {what} = 상품이나 소지품 이름
       {target} = 대상의 이름과 ID(예: 주점 f13) · {goods} = 그 가게의 상품마다 `good` 칸을 ' · ' 로 이은 것 · {id}·{name}·{price} = 상품 하나의 ID·이름·값
     · 결과 문장은 사실만 쓴다(무엇을 하라는 말 없이).
     · 이런 주석 상자 안의 글은 엔진이 읽지 않는다. 고친 뒤 `python tools/check_words.py` 로 확인한다. -->
<!-- p0.5.29 임시 문장(SilenceBreaker · 민옥 교정 대기) · p0.5.30 아래 세 칸(buy_shop · buy_other · good)도 임시 문장 -->

## `shop` — 관측 가게 줄의 머리 '- 주점 f13 — (이것):' 다음 줄부터 상품·사들이는 값({buy}·{sell})
파는 것({buy})과 사들이는 값({sell})

## `use_good` — 상품(g…)에 use 했을 때의 결과 문장({verb}·{shop}·{what})
{shop}의 상품 {what}에 {verb}을(를) 시도했다 — 아무 일도 일어나지 않았다(골드·소지품 그대로)

## `use_shop_item` — 가게에 소지품(item)을 들고 use 했을 때의 결과 문장({verb}·{shop}·{what})
{shop}에 {what}을(를) 들고 {verb}을(를) 시도했다 — 아무 일도 일어나지 않았다(골드·소지품 그대로)

## `buy_shop` — 가게(상품이 아니다)에 buy 했을 때의 결과 문장({target}·{goods})
{target}은(는) 상품이 아니다 — 파는 것: {goods}

## `buy_other` — 가게도 상품도 아닌 대상에 buy 했을 때의 결과 문장({target})
{target}은(는) 상품이 아니다

## `good` — 위 {goods} 의 상품 하나({id}·{name}·{price})
[{id}] {name} {price}골드
