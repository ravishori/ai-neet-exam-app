# PYQ Validation P2 Report — NEET 2020–2025

**Generated:** 2026-09-01T11:58:47.340348+00:00  
**Verdict:** **YELLOW**  
**Mode:** Staging validation only — no AI, no DB writes, no publication  
**Source ZIP:** `D:\ravishori\AI Neet Exam App\NEET_PYQ_OFFICIAL.zip`  
**ZIP SHA-256:** `4b5925fd554e6f3e37c446904c9b71719fc681994059c21d0f51813c610eda4a` (unchanged)  
**Staging root:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025`

## Summary

| # | Metric | Value |
|---|--------|------:|
| 1 | Papers processed | 72 |
| 2 | OCR papers processed | 31 |
| 3 | OCR pages processed | 1008 |
| 4 | OCR failures | 1008 |
| 5 | Questions extracted (TEXT) | 7679 |
| 6 | Questions requiring review | 1304 |
| 7 | missing_options resolved | 0 |
| 7b | missing_options unresolved | 0 |
| 7c | missing_options needs_review | 296 |
| 8 | ANSWER_KNOWN | 0 |
| 9 | ANSWER_PENDING | 7679 |
| 10 | ANSWER_CONFLICT | 0 |
| 11 | ANSWER_UNVERIFIED | 0 |
| 12 | Subject classified | 4799 |
| 12b | Subject UNKNOWN | 2880 |
| 12c | Subject needs review | 0 |
| 13 | 2022 gap | SOURCE_MISSING |
| 14 | Mathematics exclusions | 0 |
| 15 | Within-paper duplicates | 0 |
| 15b | Cross-paper repeats (retained) | 1487 |
| 18 | Idempotent rerun | True |
| 19 | Tests | see pytest output |
| 20 | AI calls | 0 |
| 21 | production DB writes | 0 |
| 22 | content_items modified | 0 |
| 23 | ECAEP changes | 0 |
| 24 | publication changes | 0 |

## Verdict rationale

Corpus materially improved with P2 provenance, answer classification, and missing-options triage,
but explicit validation gaps remain:

- Local Tesseract **not installed** — 1008/1008 OCR pages failed
- 296 diagram/image-option questions need human review
- 0 authoritative answers found in supplied corpus
- 2880 questions remain subject=UNKNOWN (2020 papers lack section headers)
- NEET 2022 papers: **SOURCE_MISSING**

## Checksums

```json
{
  "manifest.p2.json": "72fc3a576870e63c705536cd1fcce16b0e994c8587b2096d10f771d6f604c69b",
  "papers/00d8cababe821fcfc73db558ed7355083c52de1d3e78a073d59efa6e7c0c8fb5/questions.p2.jsonl": "03505cf55c9db7720de1691c010ba5db6b9d079d0c48344a87212358e7c97015",
  "papers/03c765a6f0172fb74a48bef5d37c8886db09a95fb7b53bf9ba25879bbe86b244/questions.p2.jsonl": "2ab543a2aa765c540fd11281af2af30ac7e05150f1ac8da3d981154e88d5a213",
  "papers/05052d6bf889fd262d3a2023e3d732bea92b68bc77ce3187647e5a357f4e928b/questions.p2.jsonl": "c67c0c86560032c6902a633740f43126dba16da41b148788686385d0385ab3fd",
  "papers/0723dcc272d0ca1eab99ec66a8ca8d1f28a02b344fb5acc825f3f23be05ab8d4/questions.p2.jsonl": "8efed3f0a778b4f71925a0d46b75f3cb815b50a146831f2f3f8fd83b86cffa57",
  "papers/0aa1b31a1609d7d4ee968c24d1c2fe71f995b3bd31ad4c2d963d7dae94e11062/questions.p2.jsonl": "783b293e1af0e0cae7e5145b1398f3736cbd5f2bedde9569acc4c2b6da79f9c2",
  "papers/0af5e1c35c8711c682a47ffbe675a98f0f2d36af1b113b5a87fafadf4dffc9c0/questions.p2.jsonl": "b8591056ef00e6bf04b0ecbca2bfc6bb8eff9eb4a43e543cf396991988e6651e",
  "papers/10030e374de702ab29f41efc33de4a1f17502d92dfcd8c48a03a0491c95e5c18/questions.p2.jsonl": "d0b69ad55812847c010611c1a68041fd219b6f5ed817c22637e4a770975c2ca9",
  "papers/140d4085a4133cfced2bb9bcd72dee7b007bd06104a56652fffd459a8cc6fce2/questions.p2.jsonl": "f93e9f9cdc96dc4b3fa735c7d7007b9ba8b85f63adca1bed48f5826f61473157",
  "papers/1944f6e974fced10a8b415d60a078fa6052662190d6bfdb9fa55858d61fc8208/questions.p2.jsonl": "c73aaee692c732fa4bbb394ecb2bde76f23332a8107690eea62ee802fe4c5b8e",
  "papers/1c21819b6d156c6fedd2aa793130a2e0146f41084dbd5e26156f0ca9245bf4eb/questions.p2.jsonl": "b3a04b48ac6a4544d51560d58a09ec7e5526cfa328970023fddef130ed122b08",
  "papers/1ca7c807db1095de925951810df1a9baf7bdd49b0c6545684c9590c7079a8e75/questions.p2.jsonl": "d575cf608a99e9a1fc89b10b49646d774a7ab291d8666de86064da8d3a580259",
  "papers/1d36ff2afae9f1d83d71fa9a867f93da9a13a37536f4e3016f99c85365829c54/questions.p2.jsonl": "be64af2cc930ed8f858c7efdee2df4897d2833ae822c28dd63b165ce8d108763",
  "papers/1d6b4be1305ce0be6d3423ce2240916f9f4f210e8f18c61149d94281d9cee5e3/questions.p2.jsonl": "e08bfc1bd8aaf08ebe20bec2a3105b28f6a5fd60014c4a4a01af4c140b88e5c4",
  "papers/1d7ffd36a442fa950eeef23ff7d5ba5a15718bf2512a3023a732f4b85ac9397e/questions.p2.jsonl": "359083b3cb6c2104e00346ebf44dba01918bd7f27581d7a0d64c59b577897e44",
  "papers/204ae2d806cddc1bda4318aba721dbe3220bcc71a2c60e9018412aaa0eaade28/questions.p2.jsonl": "b496f849ae22422efc206d695c132fe0aa868e3938bf12caf4ed79a6a138a7e0",
  "papers/2224099d43d7e83fa3e80018608ef31f65d9539733bd87ad7c6556b015d3d6ae/questions.p2.jsonl": "3c350b2ed0a3f0d56811b467e7f9dde2b8a5c9f86eb1fd4b246f9867906eb513",
  "papers/261d2b125185c0676536c02b7b56505f93fb16401ed783cc0c58f36910ac2700/questions.p2.jsonl": "d8dc2432a8d71f6f0e13beb4f64d707208b220c85279786e9ceb2bed41ac0182",
  "papers/297fcb0c37dbdddb0b96aef0ef90f43456d4cc2492221e6a0198ec71a24ca3ca/questions.p2.jsonl": "83e9a1266c34a81f7e2e033c1599c48bcea322fd47c20102ecb458e6701d0e2c",
  "papers/2b2bc0f64b041d1139556733dfdb03337051fc9e9c566a725ea77e04ac48d712/questions.p2.jsonl": "095d3fbb6c1e49478ed0a1c78562c978f408df290c01ea2a3ad3731b797db24e",
  "papers/30e4ec4ce0eaf91f0894a1211981c60d10932dad991cda2672c6f11179e4c1cc/questions.p2.jsonl": "ade13faa1ccfe527fe3248199b002c43f8e84cbff1c7282c145c39898768d9fd",
  "papers/3189e451e0263ca3b9dde0b0573ed150ad7d4aca119d2da07e4f2cf20e3b9dbf/questions.p2.jsonl": "f76915afa4e71d69d76006eb3769a932ef373329c14e0845ad973ddbae6f5d56",
  "papers/31ff7e7d0fd12436768420b056ce3f1ddc2c3866723334a4445a9b8a2d0cf6ed/questions.p2.jsonl": "d9d965e63c10b914f83144537da470596ebf970b83a89f161e02cba007942d3f",
  "papers/34ba281c8f7a45b98838714d2b01501f905fe97a140802bd117ccf082bafb302/questions.p2.jsonl": "cc2c9e169fba6b91ab0bb407adc00cd9653d4d9a0ec75466bbb0a4cb9824eb25",
  "papers/3709bf629d557fc571353c7f9e7ef35d374ba57fddd099fb0944d76b34c65229/questions.p2.jsonl": "8b066a5ea5ef916d7a4a2db25161e20e1c333cb29e885aa13e468ff7325e9d2f",
  "papers/38d7f2187e79f7a7addbac35ce2950a79ab8a12fb96eb6ed2e44c8c5021701e9/questions.p2.jsonl": "935093e061d639e8010b1eb2429e05755352fdeb1af7455732b4362214fc66e7",
  "papers/43a19fc344860688e16504ceea0987d676786fd820b83369b0262a95528f09ca/questions.p2.jsonl": "9309a88fba1ca531cdf7a8c4b076a0f9aa1b2c9540eccb4e789d9e33163398d4",
  "papers/4b21cf29952dad045f8f1282e53b9c85a9a81338c4c74bb09868870ea17b7e11/questions.p2.jsonl": "dcb4984a15c40af40e3672214bd82ee470ce2f7c81d86a94bf185f7ddba81ef7",
  "papers/530db8cab5eb3f349ce913c6c5573e8f108c8a0f1c4e32285132e02ad4eec431/questions.p2.jsonl": "d11fde422e611d40b940afa2ce5331c660ff49d4dae4642fe8b9ab7c670eb07f",
  "papers/5e94d7308a40df8b730772c37b86610553f030b737854e6b4c49d04b7eb36a40/questions.p2.jsonl": "ea33e97ced42fd2164955c280501a337a77350ac5553aeef01de4b5c572a7226",
  "papers/62a1151b273b4e9f236d135f36dae7e074f30f4967bb83acad86da34b909992a/questions.p2.jsonl": "b31ec75172634f15550f5996d86d6dd77f252ee55ae4657ff1092b2b6b93f23b",
  "papers/63da43c557c31e5b07ca9614c2e5678f54b550b461d0a794b20a7c04ed641db3/questions.p2.jsonl": "714343bc535ede961c4641cc536eaa37a6fe8d3f683db2357af8795d2b06f748",
  "papers/68144ff73f8a411969c9062f59b23fa6578d4fa5d7318612216fdffd4091369d/questions.p2.jsonl": "c8079524e303ef29e2a957c7a0441407d35e90b12c414bcb2288e20d0f2abe8c",
  "papers/6c0df3028143ff02e4210c0e583264392d4833edebfd5b3db3a71a16bf773533/questions.p2.jsonl": "ddcdd0cdd0da61959ceeb396d604a59f05bce2d53377f67b4333bc9e02b81ef4",
  "papers/6e0b5108cc4f56f6ea6d95de80cc59b7d32e6b22f4bb18cd45ffaf17838e4420/questions.p2.jsonl": "53c0305c1142c4260bbf71219e7766d67ebbfad5046f484c6832d63c08889ae7",
  "papers/6fc07a7516fa48e1ec4eef9d1df1311ecc0c75fd351116520904963ad358a602/questions.p2.jsonl": "f9ba592955efbfb11a443cddd575f5c3471617cec64f1c581b25d5f1109b69a0",
  "papers/7a50306cbc82553899a35e0679d65ed89d5660d6262787e600453c9e5d1e221e/questions.p2.jsonl": "b88a94bcb21433341f409f4598c7bc669898e026a70ee4249bedc615164cc83b",
  "papers/7e4dabb5a199588d433e77360860bcda61574e363dd571513901ff778b50004f/questions.p2.jsonl": "8cf7188c66ac3e11f51108df5a5e0146cab688e371e6b6f9e9d2e1f144035e1a",
  "papers/7e6acf734cf5d0db6bd6f826c05f8a558381ae1ff844287d2075dd9288ce208c/questions.p2.jsonl": "3dc8e8ea7643c53e36348dc0e0f53202ef94177e049b17f02458382d2142421b",
  "papers/82a7cff8dca5bb403d468485e41216cfe975175acaea927f0c2f32ce4904c2c3/questions.p2.jsonl": "2bd170b51561a300f29f653212bc11e807c5a4a920837785e404478d5e627a13",
  "papers/82e3f43336780eb9a7ae1bf65e7efb5d2f13708de079f93bbb07acf9027a749b/questions.p2.jsonl": "7e0be3674bd531e224bc9034da07f32789be8b06840f62504f9f49e84cea61c2",
  "papers/8633a3811ea0744796e1593f0567e619468d239bea9c24daf7f768a775ccd4d0/questions.p2.jsonl": "98776e44c82585f6f1e902e444a8200e70c10cd1b129a258b0573c4d3135a1cc",
  "papers/87c534cad98b7b4e0b1fc7c74134f2043ceac60a8e7756aefc915a8f3426a324/questions.p2.jsonl": "49411a9c174de56694be49c17f1053ce1db606035bbd053516743e93ce06dad1",
  "papers/88090c6221f71f0550378e4d73bf5f3dd21585ce3cb5fd0ee712cc5ac2d57608/questions.p2.jsonl": "d24ccf097af9758b3d4f02ab81e5739c11627078bcadd4a0eb88998c5d3015c6",
  "papers/91849671f4fa7f3bb14baa8bfe496e96a0aacf2aa4a6e387c37971850b941de3/questions.p2.jsonl": "f5328297f55f6faee736ee146a09fc0c6fde7190f19ad95574e73e22b661c5a4",
  "papers/9fcfff3f3335090755c66e3aa7c850ad762888c80d331c0376a63e0d7c189f46/questions.p2.jsonl": "a917fcfc508aeefdd9cd563887d3dfb002c15d53823bd5ea7d13ca0d08e2a332",
  "papers/a0dac1c078a1a10ee4bac7166108c18ac22adc9523b81c0fab8e43cdf62fd36a/questions.p2.jsonl": "965d8fc23aefc0c4b279f2f7c5793efa321b6db44d4afed186181520a799d289",
  "papers/a1c3361678271d6e128e7b9eb4cc814dec903bbfab808d82fa520a58e8f39e00/questions.p2.jsonl": "e6bb9f02498ac5d2f84d036ae558bf9a8d9dda21f5f38f93284a4ee4e781b79b",
  "papers/a43894b5fbc8cd2891bc7ba56aff3b8682960995783a8b3a488be3fa8fe030eb/questions.p2.jsonl": "390a67fb3c0cd2a44058d099b9997637c97d0130530e51b840dab0df108b9ed8",
  "papers/a6944ae5587d0d623dc8cac8f34505244b88bbd841e1d62297fb24ab7132517d/questions.p2.jsonl": "3a4db41b057daeeda006fb3deecfc1ed2c7a028871b1c47f4b99bb9742ce93f3",
  "papers/ab6f81f954d1c61c2b2fa0577037c82e4f9db8c5c699449c2f80a1ebef2194bb/questions.p2.jsonl": "7bda44ffa4a72e60a48a558bad8f96a2c7be6a1b5fb7c40de610818155b95333",
  "papers/aec30fb24ab1cc837d967a6dd30a3f3babfbdf028fbc8272d220881a37e9d033/questions.p2.jsonl": "fb3b2d8d5e562b04754cee578cc8cdaf01c7eb3e766090182c5236e3691fabe1",
  "papers/b5d60d96f61522f2be85ce7086a99ba3a139ada136d377a34a9903eabe2b220c/questions.p2.jsonl": "8c86de3c6a4262977fc0f7483ac02665c2b5928ea47ee8b728dd7b321f35f73e",
  "papers/b69d582ff457c62ec07e83298ec42c4041d7048293e39e58d05f93307e7b6dd1/questions.p2.jsonl": "723085340fcd7c6fb4f5bdc84bc9a0a7e2ed847c56ad7a3d60443f7280fef47e",
  "papers/c07332f2ee9b48ff35c1b32e7b2bf087a19cdf4989834334472c74f3e11085de/questions.p2.jsonl": "8a486d7ec0366c1b34bc8c21d57d99ced6313560ae01c206e7ce7b3fe85a3c27",
  "papers/c7075d2a0f5485408d2613967e5e6b551409a06bb7a65a42f667a2b5aab34d41/questions.p2.jsonl": "47e9f7c49a50355baf0db392d041ae74dd551989117b118197041841a5ed092d",
  "papers/cd4583ce844d9f5c55c9d2998710cf2915d41bc2e40bf76997178056d3a5044f/questions.p2.jsonl": "630c609fbe262e2d510bb8e815bc8c852ac197764c513e76e7c8e5d2666e734b",
  "papers/cf69a2a4a46e6ce451f23490fda4db1cf5021879e6ace71d0fb2be7aacb36eff/questions.p2.jsonl": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "papers/d02f7f096fa6a031fdca523c24c69334da06f01bc20af5551b3de3c96a700eee/questions.p2.jsonl": "8675d13f3e881dd106732f44f677bc0aae2982d8e3091a75ae8c6aec5852a1cb",
  "papers/d070925aa0d4647597d71bc9f88c6d7fd5a603b6f084f063d33aee1aeebe7985/questions.p2.jsonl": "4718755cb12f0d7f946436ca79628124f9e1ac4e3e7dbcf54fe903905900c798",
  "papers/d11cf53d4d8ef5b08ed85ccfd5b46081623475f45bda9e5c5c789ffcc9b1ca08/questions.p2.jsonl": "4ff848c74667558e81bb5d62b215fe37c5a557350e11d2da4e8f5c20c277c85d",
  "papers/db0d8d8c3ace383fa65e122d9cdb0a097f530726e99ae487ecde07dd6617b2dc/questions.p2.jsonl": "3a68068bb37dd4cdf5c437987aad251a5d4ca0411253a6084f6a9af23d0e127f",
  "papers/dbdcfa0a13d1346782a88d32dff405a920d4cd72e6b32bd577e3508da8beb46c/questions.p2.jsonl": "31ac5d8ad80742260c34ae77ccb71e413f3343900dd3fec45267276fc96d51c4",
  "papers/dd685818878dd64fbe3b1314cdd292acbe4ab97279b6d0819505402958c8ef5d/questions.p2.jsonl": "1b2a0519caf6824986f82be62d9b9a8be8cf1e5a8421bf9e246cb4f6bb10efe7",
  "papers/df0707ec85be46167a8805539074cfca4f0fee6a9e1c42dbf7894d44c2bd936a/questions.p2.jsonl": "00d1d7ee605711ab0536bf5c5fae7437240ca2aeca6a502759dfc470257bbbd8",
  "papers/e1e840ca88f39a9d679eb7181dcaef7c2151d64306aef41a4d8aa4ef11fac31d/questions.p2.jsonl": "903b0f9484a0f31d153d393fb3cf48ea84a090f2110119becb3b98a049d50173",
  "papers/e621c104412ba07eb22cce97b56f2d57f99d022a0de654fe6c719ec8bcbb8a2c/questions.p2.jsonl": "8c790122d51e011f7b668ebc91f56aec493fe0ddc9dca528336a0368a9c2bd73",
  "papers/e9acdfb29dfcff0a3a186819f7336330af4ce51855990d1081c78637b338587a/questions.p2.jsonl": "ec90f6fc179d1d64624bd3eb72fbfc53be58cd33ad57e5c3042594b90f7407ea",
  "papers/ee3990aec2dfa279a51191ca58f59e903e17a419d961bbd03db2620b9534436e/questions.p2.jsonl": "86f04a7a21ea017e0c7778b030a9660c77c9f54acf5b7874af7cb99274849e53",
  "papers/f46063650ca02ee513201e7711ebfe7c5da4b7f5d4befd6162e0049aada1c35d/questions.p2.jsonl": "4e143b8f3b53c4f4e3120caeabebb1d6ec8802a5a21df4044836ceb722372cd2",
  "papers/f5378eb6785774c36b1507b9f74db4655eb12e00ccf49c088babf9a14154f406/questions.p2.jsonl": "bfb7183a8092c3d1975ba7f3f95fd23a4f80db782d4d85defcde0ff756d1518b",
  "papers/f7a45c960ede2f29d81df2d6fa789391872668cd71121780a861a04a53edad87/questions.p2.jsonl": "d8de70f370da58213be53bc4f4d5a916889321d1620777f57f6834c68b39d1bc",
  "papers/ff76c4667e7ac6a2628830992ab0dc356d69a4b00f4e7163721288741b6c9ed9/questions.p2.jsonl": "ebf90156b349fcf7a6c90febe66f9ec9caee1799040f66dccf07022ee9fcc5d2",
  "all_questions.p2.canonical": "c8b6e9ffbabec0b3854f83e16904f7f3bebf0db5459452e247035b5e1cd81c70"
}
```

## Safety attestation

| Check | Value |
|-------|------:|
| ai_provider_calls | 0 |
| production_db_writes | 0 |
| content_items_modified | 0 |
| ecaep_changes | 0 |
| publication_changes | 0 |
| source_zip_modified | 0 |

**STOP.** No production database import. Await explicit authorization for P3.
