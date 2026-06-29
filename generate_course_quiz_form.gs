/**
 * 橘子蘋果課程體系 50 題測驗 Google Form 產生器（線上版，已移除實體相關題目）
 * 使用方式：
 *   1. 開 script.google.com → 新增專案
 *   2. 貼入全部程式碼
 *   3. 點「執行」→ createCourseQuizForm
 *   4. 授權後等待，執行完畢會在 console 印出 Form 連結
 */

function createCourseQuizForm() {
  const form = FormApp.create('橘子蘋果課程體系測驗（課程顧問）');
  form.setDescription('確認對橘子蘋果全部線上課程產品的熟悉程度。共 50 題、每題 2 分，滿分 100 分。');
  form.setIsQuiz(true);
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);

  const questions = [

    // ── 玩創系列 ── (Q1~12)
    {
      title: 'Q1｜頑皮艾伯特主要招收哪個年級？',
      choices: ['1～2 年級', '3～4 年級', '5～6 年級', '國一以上'],
      correct: 0
    },
    {
      title: 'Q2｜頑皮艾伯特線上正式班的師生比是？',
      choices: ['1:6', '1:9', '1:10', '1:5'],
      correct: 0
    },
    {
      title: 'Q3｜頑皮艾伯特共幾堂課？',
      choices: ['36 堂', '30 堂', '15 堂', '60 堂'],
      correct: 0
    },
    {
      title: 'Q4｜以下哪種課程允許學生使用平板上課？',
      choices: ['頑皮艾伯特', 'Scratch 實戰班', 'Python 程式開發班', 'Roblox 遊戲設計班'],
      correct: 0
    },
    {
      title: 'Q5｜STEAM 創意機械積木班共幾堂、分幾個階段？',
      choices: ['60 堂、4 階段', '36 堂、3 階段', '30 堂、2 階段', '45 堂、3 階段'],
      correct: 0
    },
    {
      title: 'Q6｜麥塊班線上點數制，45 點 + 3 套教材合購底價是？',
      choices: ['45,500 元', '36,500 元', '42,000 元', '48,000 元'],
      correct: 0
    },
    {
      title: 'Q7｜Minecraft 麥塊程式班最低招收年級是？',
      choices: ['國小 3 年級', '國小 1 年級', '國小 4 年級', '國小 5 年級'],
      correct: 0
    },
    {
      title: 'Q8｜麥塊班線上正式班師生比是？',
      choices: ['1:7', '1:5', '1:10', '1:6'],
      correct: 0
    },
    {
      title: 'Q9｜麥塊班共分幾個階段？',
      choices: ['3 階段', '2 階段', '4 階段', '5 階段'],
      correct: 0
    },
    {
      title: 'Q10｜Roblox 班招收條件，以下何者正確？',
      choices: ['麥塊進階班畢業，或完全無經驗的 3 年級以上', '僅限麥塊進階班畢業生', '1 年級以上皆可', '國中以上才能報名'],
      correct: 0
    },
    {
      title: 'Q11｜Roblox 跳級測驗滿分（120 分）可從第幾堂開始？',
      choices: ['L9', 'L7', 'L4', 'L1'],
      correct: 0
    },
    {
      title: 'Q12｜以下哪個玩創課程目前「不再招收新生」？',
      choices: ['Boson 創意電子樂高班', 'Roblox AI 遊戲設計班', 'STEAM 創意機械積木班', '頑皮艾伯特'],
      correct: 0
    },

    // ── 菁英系列 ── (Q13~26)
    {
      title: 'Q13｜菁英系列共幾個階段？',
      choices: ['9 階段', '6 階段', '7 階段', '8 階段'],
      correct: 0
    },
    {
      title: 'Q14｜菁英系列「第 1 階段」課程名稱是？',
      choices: ['Scratch 實戰班（SB）', 'Python 程式開發班（PYB）', 'Scratch 菁英班（SA）', 'JavaScript 程式開發班（JS）'],
      correct: 0
    },
    {
      title: 'Q15｜菁英系列「第 9 階段」是哪門課？',
      choices: ['AI 人工智慧班', 'AI 思維：實戰問題解決課', '演算法研究與應用班', '網路與資料庫應用班'],
      correct: 0
    },
    {
      title: 'Q16｜國一以上的新生，無程式經驗，應從菁英哪個階段開始？',
      choices: ['Python 程式開發班（第 3 階段）', 'Scratch 實戰班（第 1 階段）', 'JavaScript 程式開發班（第 5 階段）', 'Scratch 菁英班（第 2 階段）'],
      correct: 0
    },
    {
      title: 'Q17｜菁英系列每個階段幾堂、每堂幾小時？',
      choices: ['15 堂、2 小時', '10 堂、3 小時', '20 堂、1.5 小時', '12 堂、2 小時'],
      correct: 0
    },
    {
      title: 'Q18｜菁英初階（Scratch）線上正式班師生比是？',
      choices: ['1:9', '1:6', '1:10', '1:7'],
      correct: 0
    },
    {
      title: 'Q19｜Scratch 測驗 150 分以上，可直接跳到菁英哪個階段？',
      choices: ['Python 第 1 堂', 'SA 第 1 堂', 'JS 第 1 堂', 'SB 第 7 堂'],
      correct: 0
    },
    {
      title: 'Q20｜Python 測驗 80 分以上，可跳到菁英哪個位置？',
      choices: ['JS 第 1 堂', 'PYA 第 1 堂', 'PY 第 11 堂', 'PY 第 6 堂'],
      correct: 0
    },
    {
      title: 'Q21｜菁英線上點數制，初階（Scratch）教材費是多少？',
      choices: ['9,000 元', '12,000 元', '6,000 元', '13,500 元'],
      correct: 0
    },
    {
      title: 'Q22｜菁英線上點數制，中階（Python／JS／H5）教材費是多少？',
      choices: ['12,000 元', '9,000 元', '13,500 元', '6,000 元'],
      correct: 0
    },
    {
      title: 'Q23｜菁英線上點數制，高階（DB／AL／AI）教材費是多少？',
      choices: ['13,500 元', '12,000 元', '9,000 元', '15,000 元'],
      correct: 0
    },
    {
      title: 'Q24｜8 年級以上無程式經驗，應從菁英哪個階段開始？',
      choices: ['JavaScript 程式開發班（第 5 階段）', 'Python 程式開發班（第 3 階段）', 'Scratch 實戰班（第 1 階段）', 'HTML5 網頁程式開發班（第 6 階段）'],
      correct: 0
    },
    {
      title: 'Q25｜菁英系列採用哪種上課模式？',
      choices: ['雙師模式', '單師模式', '錄播模式', '自學模式'],
      correct: 0
    },
    {
      title: 'Q26｜菁英線上點數制，3 階段合購底價（各含教材）約多少？',
      choices: ['47,000 元', '50,500 元', '42,000 元', '55,000 元'],
      correct: 0
    },

    // ── 駭客系列 ── (Q27~36)
    {
      title: 'Q27｜APCS 程式檢定班招收最低年級是？',
      choices: ['8 年級', '6 年級', '5 年級', '7 年級'],
      correct: 0
    },
    {
      title: 'Q28｜APCS 初階班目標是通過哪個等級的成績？',
      choices: ['識讀 3、實作 2', '識讀 4、實作 3', '識讀 2、實作 1', '識讀 5、實作 4'],
      correct: 0
    },
    {
      title: 'Q29｜APCS 初階課程共幾堂、每堂幾小時？',
      choices: ['10 堂、3 小時', '15 堂、2 小時', '8 堂、3 小時', '12 堂、2.5 小時'],
      correct: 0
    },
    {
      title: 'Q30｜ITS Python 全球認證班線上版本規劃幾週？',
      choices: ['9 週', '8 週', '6 週', '12 週'],
      correct: 0
    },
    {
      title: 'Q31｜ITS Python 全球認證班底價是？',
      choices: ['22,800 元', '23,800 元', '21,800 元', '24,800 元'],
      correct: 0
    },
    {
      title: 'Q32｜ITS Python 沒考過可以半價重修，重修費是？',
      choices: ['11,900 元（含測驗費 3,300）', '12,000 元', '10,500 元', '15,000 元'],
      correct: 0
    },
    {
      title: 'Q33｜ITS 目前共有幾張證照可以考？',
      choices: ['4 張（Python／JavaScript／HTML&CSS／運算思維）', '2 張', '3 張', '5 張'],
      correct: 0
    },
    {
      title: 'Q34｜ITS JavaScript 班招收條件，以下何者正確？',
      choices: ['修畢菁英第 5 或第 6 階段，或 7 年級以上', '僅限修完 Python 班', '5 年級以上皆可', '國中以上無任何條件'],
      correct: 0
    },
    {
      title: 'Q35｜以下哪個駭客課程目前「暫不開班」？',
      choices: ['TQC+ APP Inventor 手機程式認證班', 'APCS 程式檢定 Python 班', 'ITS Python 全球認證班', 'ITS JavaScript 全球認證班'],
      correct: 0
    },
    {
      title: 'Q36｜APCS 班有沒有試聽？',
      choices: ['沒有試聽', '有一般試聽', '有能力測驗體驗課', '視報名人數決定'],
      correct: 0
    },

    // ── 麥思數學 ── (Q37~40)
    {
      title: 'Q37｜橘蘋麥思數學目前開課形式為？',
      choices: ['僅線上', '僅實體', '線上與實體都有', '均暫停'],
      correct: 0
    },
    {
      title: 'Q38｜麥思數學 Level 2 最適合幾年級？',
      choices: ['小 1 以上（最佳小 2～3）', '小 3～4', '小 4～5', '小 5～6'],
      correct: 0
    },
    {
      title: 'Q39｜麥思線上正式班師生比是？',
      choices: ['1:6', '1:5', '1:4', '1:8'],
      correct: 0
    },
    {
      title: 'Q40｜麥思線上試聽後買 14 次，底價是？',
      choices: ['6,300 元（約 450 元/次）', '8,000 元', '5,600 元', '7,200 元'],
      correct: 0
    },

    // ── AI 思維課 ── (Q41~43)
    {
      title: 'Q41｜AI 思維：實戰問題解決課招收最低年級是？',
      choices: ['5 年級', '4 年級', '7 年級', '國一'],
      correct: 0
    },
    {
      title: 'Q42｜AI 思維課新生/試聽優惠價是？',
      choices: ['16,500 元', '24,000 元', '15,500 元', '18,000 元'],
      correct: 0
    },
    {
      title: 'Q43｜AI 思維課師生比是？',
      choices: ['1:10', '1:6', '1:15', '1:9'],
      correct: 0
    },

    // ── 線上營隊 ── (Q44~47)
    {
      title: 'Q44｜線上 APCS 檢定培訓營費用是多少？',
      choices: ['39,800 元（5 天 30 小時）', '20,000 元', '12,500 元', '29,800 元'],
      correct: 0
    },
    {
      title: 'Q45｜線上課程（現行規定）可以使用平板上課嗎？',
      choices: ['不可以（線上課程一律不可用平板）', '可以，任何課程皆可', '只有麥思可以', '視老師決定'],
      correct: 0
    },
    {
      title: 'Q46｜線上 Python 遊戲體驗營適合哪個年級？',
      choices: ['國一～高三', '小 3～6', '小 4～國一', '7～12 年級'],
      correct: 0
    },
    {
      title: 'Q47｜線上 Scratch 遊戲體驗營（密集雙師）適合哪個年級？',
      choices: ['小 4～國一', '小 3～6', '國一～高三', '小 1～3'],
      correct: 0
    },

    // ── 招生通則 ── (Q48~50)
    {
      title: 'Q48｜年齡不符的學生若要安排試聽，需要送什麼？',
      choices: ['Omni 特殊個案處理單', '直接安排，不需審核', '先送主管口頭確認', '填寫 Google Form 申請'],
      correct: 0
    },
    {
      title: 'Q49｜信用卡 12 期分期，線上課程費用超過多少才需疊價 5%？',
      choices: ['30,000 元', '45,000 元', '20,000 元', '50,000 元'],
      correct: 0
    },
    {
      title: 'Q50｜駭客班團報優惠適用條件，以下何者正確？',
      choices: ['僅限 2 人報駭客課，或 1 人報 2 檔駭客課', '任何 2 人以上皆可團報', '可與玩創/菁英合併計算', '3 人以上才符合'],
      correct: 0
    }
  ];

  questions.forEach((q) => {
    const item = form.addMultipleChoiceItem();
    item.setTitle(q.title);
    item.setPoints(2);
    const choiceObjs = q.choices.map((text, idx) =>
      item.createChoice(text, idx === q.correct)
    );
    item.setChoices(choiceObjs);
    item.setRequired(true);
  });

  const url = form.getPublishedUrl();
  const editUrl = form.getEditUrl();
  Logger.log('✅ 表單建立完成！');
  Logger.log('📋 填答連結（給新人）：' + url);
  Logger.log('✏️  編輯連結（給 Posh）：' + editUrl);
}
