#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
 即梦(Seedance) 批量「图生视频」脚本  ——  绕开消费版即梦的排队 / 高峰期
===========================================================================
这是给《最后一面》用的：把你已经做好的【角色多视图 / 关键帧】图片，
批量提交给火山引擎上的「即梦视频生成」API，自动等待、自动下载 mp4。

  它解决的痛点：消费版即梦网页版排队、"高峰期发不出去"。API 走的是另一条
  企业通道，不排你在消费端那条队，提交即处理。

  ⚠️ 重要（你说没钱，一定先看）：
  1) API 是【按次付费】的（不像会员"无限但排队"）。开工前先在火山引擎
     后台确认单价、充一点点额度测试；跑之前脚本会问你确认。
  2) 免费替代方案见 README_使用说明.md ——「即梦生成」那节。没预算就先用免费法。

---------------------------------------------------------------------------
 一、准备（一次性，约 10 分钟）
---------------------------------------------------------------------------
  1. 电脑装 Python 3，然后装 SDK：
        pip install volcengine
  2. 注册/登录火山引擎 → 开通「视觉智能 / 即梦AI」视频生成服务：
        https://www.volcengine.com/product/jimeng
  3. 在火山引擎控制台「访问控制 / 密钥管理」拿到 Access Key 和 Secret Key，
     填到下面 AK / SK。
  4. 打开即梦视频生成的【接口文档】，把你要用的模型的 req_key 复制进来
     （下面 REQ_KEY）。文档入口（图生视频 3.0 720P 等）：
        https://www.volcengine.com/docs/85621/1785201
        （文档里每个模型页顶部都会给出该模型对应的 req_key 字符串）

---------------------------------------------------------------------------
 二、使用
---------------------------------------------------------------------------
  - 把参考图放进 ./frames/ 文件夹（jpg/png）。
  - 在 PROMPT 里写"微动"提示词（呼吸感、自然眨眼、头发飘动、光影变化…），
    运动幅度别贪大，成功率最高、最有电影感。
  - 运行：  python jimeng_batch.py
  - 生成好的视频落在 ./videos/ ，文件名和参考图对应。
===========================================================================
"""

import os, time, json, base64, sys, urllib.request

# ============ 你需要填的 4 个东西 ============
AK        = "在这里填你的_ACCESS_KEY"
SK        = "在这里填你的_SECRET_KEY"
REQ_KEY   = "在这里填_模型req_key"      # 从上面接口文档对应模型页复制
PROMPT    = "呼吸感, 自然眨眼, 头发随风飘动, 光影缓慢变化, 慢动作, 电影质感, 35mm镜头"
# ============================================

IN_DIR   = "frames"     # 参考图文件夹
OUT_DIR  = "videos"     # 输出文件夹
POLL_SEC = 8            # 每隔几秒查询一次结果
MAX_WAIT = 600          # 单个任务最长等待秒数

def die(msg):
    print("✗", msg); sys.exit(1)

def confirm_cost():
    print("=" * 60)
    print(" 提醒：即梦 API 按次计费。这次会提交", "多个" , "任务，会产生费用。")
    print(" 没预算就先用 README 里的免费方案。")
    ans = input(" 确认继续并已充值额度？(yes/no) ").strip().lower()
    if ans not in ("y", "yes"): die("已取消。")

def img_to_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def main():
    try:
        from volcengine.visual.VisualService import VisualService
    except ImportError:
        die("未安装 SDK，请先运行:  pip install volcengine")

    if "填" in AK or "填" in SK or "填" in REQ_KEY:
        die("请先在脚本顶部填好 AK / SK / REQ_KEY（见文件开头说明）。")

    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.isdir(IN_DIR):
        die(f"找不到参考图文件夹 ./{IN_DIR}/ ，请先建好并放入图片。")

    imgs = [f for f in sorted(os.listdir(IN_DIR))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not imgs:
        die(f"./{IN_DIR}/ 里没有图片。")

    print(f"发现 {len(imgs)} 张参考图。")
    confirm_cost()

    vs = VisualService()
    vs.set_ak(AK); vs.set_sk(SK)

    for name in imgs:
        stem = os.path.splitext(name)[0]
        out_path = os.path.join(OUT_DIR, stem + ".mp4")
        if os.path.exists(out_path):
            print(f"↷ 已存在，跳过：{out_path}"); continue

        print(f"\n▶ 提交：{name}")
        b64 = img_to_b64(os.path.join(IN_DIR, name))
        submit_form = {
            "req_key": REQ_KEY,
            "binary_data_base64": [b64],   # 用本地图片（图生视频）
            "prompt": PROMPT,
            # 下面这些参数不同模型名字可能略有差异，以接口文档为准：
            # "aspect_ratio": "16:9",
            # "seed": -1,
        }
        try:
            r = vs.cv_sync2async_submit_task(submit_form)
        except Exception as e:
            print("  提交失败：", e); continue

        task_id = (r or {}).get("data", {}).get("task_id")
        if not task_id:
            print("  未拿到 task_id，返回：", json.dumps(r, ensure_ascii=False)[:300]); continue
        print("  task_id:", task_id, "  等待生成…")

        # 轮询结果
        waited, video_url = 0, None
        while waited < MAX_WAIT:
            time.sleep(POLL_SEC); waited += POLL_SEC
            try:
                q = vs.cv_sync2async_get_result({"req_key": REQ_KEY, "task_id": task_id})
            except Exception as e:
                print("  查询异常：", e); continue
            data = (q or {}).get("data", {})
            status = data.get("status") or data.get("task_status")
            # 不同模型字段名可能是 video_url / resp_data 里的链接，按文档取
            video_url = data.get("video_url") or data.get("url")
            if video_url:
                break
            if status in ("failed", "FAILED", "not_found"):
                print("  生成失败，status =", status); break
            print(f"  …{waited}s（{status}）")

        if not video_url:
            print("  超时或失败，跳过。"); continue

        try:
            urllib.request.urlretrieve(video_url, out_path)
            print(f"  ✓ 已保存：{out_path}")
        except Exception as e:
            print("  下载失败：", e, "\n  视频地址：", video_url)

    print("\n全部处理完毕。视频在 ./%s/ 。" % OUT_DIR)

if __name__ == "__main__":
    main()
