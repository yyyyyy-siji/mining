"""Phase 8 — Generate 50 AIGC video sample records for end-to-end validation.

Each record simulates a viral AIGC short-video from B站 / 抖音 / 小红书,
covering 10 content categories with realistic titles, descriptions, and
engagement metrics.

Usage:
    cd /path/to/signal-miner
    .venv/bin/python scripts/generate_aigc_video_samples.py
"""

from __future__ import annotations

import asyncio
import hashlib
import random

# ── Category definitions ──

CATEGORIES = {
    "ai_art": {
        "cn": "AI绘画/生成艺术",
        "sources": ["bilibili", "douyin", "xiaohongshu"],
        "titles": [
            "Midjourney V7 出图质量碾压SD3，这套提示词模板直接封神",
            "用Stable Diffusion复刻了新海诚风格，每一帧都是壁纸",
            "ComfyUI工作流分享：一键出图+自动高清放大，效率提升10倍",
            "AI绘画已经进化到这种程度了？这10组作品让人头皮发麻",
            "Flux+LoRA组合技，生成的人物终于不再恐怖谷了",
        ],
        "descriptions": [
            "这期和大家详细拆解我常用的Midjourney提示词模板，从构图到光影全部讲清楚。",
            "花了一周时间调试这个ComfyUI工作流，终于稳定了，分享给大家。",
            "对比了SD3和Flux在相同prompt下的出图效果，差距太明显了。",
            "这期教程从零开始教你用LoRA训练自己的风格模型，上手超简单。",
            "整理了50组实测好用的AI绘画prompt，涵盖电影感、二次元、写实三个方向。",
        ],
        "comments": [
            "太牛了，这个色彩搭配真的绝了，求prompt！",
            "跟着教程做了一遍，出图质量直接提升了一个档次",
            "已三连，这种干货教学多多益善",
            "ComfyUI那部分讲得太清晰了，新手也能看懂",
            "3秒那个开场特效是怎么做的？太吸引人了",
        ],
    },
    "ai_video": {
        "cn": "AI视频生成",
        "sources": ["bilibili", "douyin", "xiaohongshu"],
        "titles": [
            "Kling 2.0 实测：Sora平替终于来了，文生视频效果炸裂",
            "用Runway Gen-3做了一支概念短片，导演看了都说好",
            "Pika 2.0更新了运动笔刷功能，这个转场骚操作你绝对想不到",
            "零基础入门AI视频制作：从生成到剪辑一站式教程",
            "海螺AI生成视频+剪映自动剪辑，10分钟出一支高质量短片",
        ],
        "descriptions": [
            "实测Kling 2.0文生视频效果，对比了和Runway/Sora在运镜、光影、一致性方面的差异。",
            "这期用Runway Gen-3做了一支3分钟的概念短片，从分镜到成片全程记录。",
            "Pika 2.0新出的运动笔刷功能太强了，可以精确控制画面中每个元素的运动轨迹。",
            "教程系列第3期：如何用AI视频工具搭配传统剪辑软件做高质量内容。",
            "海螺AI免费额度就能做高质量视频，这期教你最大化利用免费资源。",
        ],
        "comments": [
            "前3秒那个转场怎么做的？直接划走的人都得划回来",
            "BGM配得太绝了，叫啥名字？",
            "跟着教程做了一个，播放量直接破万，感谢！",
            "Kling的效果确实比想象的好，但是生成速度还是有点慢",
            "这个教程太实用了，已收藏",
        ],
    },
    "ai_music": {
        "cn": "AI音乐创作",
        "sources": ["bilibili", "douyin"],
        "titles": [
            "用Suno AI做了一首周杰伦风格的情歌，朋友以为是新专辑",
            "AI写歌也太强了吧！3分钟出完整编曲+歌词+人声",
            "Udio vs Suno终极对决：哪个AI更适合做BGM？",
            "把《原神》BGM喂给AI重新编曲，效果燃爆了",
            "新手教程：用AI工具0成本做一首原创歌曲，全流程拆解",
        ],
        "descriptions": [
            "这期用Suno AI的V4模型做了一首完整的原创歌曲，从风格选择到最终母带全部展示。",
            "对比了Suno和Udio在旋律创作、人声自然度、多语种支持方面的差异。",
            "AI音乐工具现在能生成电影级配乐了，这期演示完整工作流。",
            "教程系列：手把手教你用AI做一首能上音乐平台的歌。",
            "AI生成的BGM居然不输专业制作？这期视频颠覆你的认知。",
        ],
        "comments": [
            "这是什么神仙配乐，氛围感直接拉满",
            "副歌部分太好听了，单曲循环中",
            "Suno的编曲能力真的离谱，感觉比很多独立音乐人强",
            "建议UP主出个教程教怎么调prompt",
            "这个视频的节奏控制得太好了，每个段落衔接丝滑",
        ],
    },
    "ai_digital_human": {
        "cn": "AI数字人/虚拟主播",
        "sources": ["bilibili", "douyin", "xiaohongshu"],
        "titles": [
            "用HeyGen做了一个AI数字人，24小时不间断直播带货",
            "AI虚拟主播上岗第一天就火了，观众以为是真人在线",
            "数字人短视频创作教程：一个人就是一个团队",
            "D-ID vs HeyGen vs 硅基智能：3大数字人平台横评",
            "AI数字人带货实测：7天GMV翻3倍的秘诀",
        ],
        "descriptions": [
            "这期实测HeyGen制作数字人短视频的全流程，从形象定制到口型同步到多语种克隆。",
            "横评了市面上主流的AI数字人平台，从价格、效果、易用性三个维度对比。",
            "用数字人做了一个月短视频，播放量从几百涨到几十万，分享一下经验。",
            "AI数字人+ChatGPT自动生成脚本+剪映自动剪辑，实现短视频全自动化。",
            "数字人直播带货实操：选品策略+话术脚本+数字人配置全方案。",
        ],
        "comments": [
            "这个数字人的微表情做得太逼真了，完全看不出来是AI",
            "开头那个口型同步简直以假乱真，技术太可怕了",
            "教程讲得很细，适合小白上手",
            "请问用的什么平台？成本大概多少？",
            "4秒那里的表情变化太自然了，是怎么调参的？",
        ],
    },
    "ai_face_swap": {
        "cn": "AI换脸/换装",
        "sources": ["douyin", "xiaohongshu"],
        "titles": [
            "用AI把自己换进了《流浪地球3》预告片，毫无违和感",
            "这个换装AI太懂女生了！一键试穿全网任意款式",
            "AI穿越到100年前的老照片里，家人看到直接哭了",
            "用FaceFusion给自己做了个古装剧角色，朋友以为我进组了",
            "AI拍照神器的背后：换脸+换装+换场景一条龙测评",
        ],
        "descriptions": [
            "这期用FaceFusion做了一个影视剧换脸效果，把流程全部拆解出来。",
            "测评了5款AI换装工具，从效果、速度、隐私保护三个维度打分。",
            "AI换脸技术现在门槛有多低？一个教程让你10分钟上手。",
            "用AI让自己穿越到不同的时代和场景，这个效果太震撼了。",
            "AI拍照神器深度测评：真的能做到一键出大片吗？",
        ],
        "comments": [
            "这换脸效果太自然了，细节处理绝了",
            "开头那个穿越特效怎么做的，求教程！",
            "已被安利，马上去试试",
            "笑死，换到古装剧里那个表情也太到位了吧",
            "这个创意的点子太妙了，自己也想去试一下",
        ],
    },
    "ai_editing": {
        "cn": "AI辅助剪辑/特效",
        "sources": ["bilibili", "douyin"],
        "titles": [
            "AI自动剪辑工具实测：素材丢进去3分钟出成片",
            "用AI抠图+跟踪特效，一个人做出百万UP主的后期质感",
            "剪映AI功能全解：这5个隐藏功能让你的视频质感翻倍",
            "CapCut vs 剪映：两大AI剪辑工具终极对比",
            "AI自动生成字幕+翻译+配音，做多语种内容的效率神器",
        ],
        "descriptions": [
            "测评了目前市面上最好用的AI自动剪辑工具，对比输出质量和工作效率。",
            "手把手教你用AI抠图+运动跟踪+特效合成，一个人完成后期全流程。",
            "这期分享5个剪映AI隐藏功能，每个都能让你的视频质感提升一个档次。",
            "CapCut和剪映的AI功能全面对比，到底哪个更适合中文创作者？",
            "AI字幕+翻译+配音一站式工具测评，做海外内容的效率直接起飞。",
        ],
        "comments": [
            "这个转场特效也太丝滑了吧，用的什么工具？",
            "第5个功能真的绝了，之前从来不知道还能这样用",
            "节奏感掌控得太好了，每个剪辑点都在音乐重拍上",
            "这期教程质量太高了，已投币",
            "AI自动剪辑省太多时间了，创作者福音",
        ],
    },
    "ai_prompt_engineering": {
        "cn": "Prompt工程教程",
        "sources": ["bilibili", "xiaohongshu"],
        "titles": [
            "这个Prompt框架让我出图率提升了300%，AI绘画必看",
            "Prompt Engineering入门到精通：7个核心技巧全拆解",
            "我把1000组爆款AI绘画Prompt做了数据分析，发现了这些规律",
            "为什么你的AI画不出好图？90%的人忽略了这3个Prompt细节",
            "不是AI不行，是你的Prompt不行！高阶Prompt设计思维",
        ],
        "descriptions": [
            "整理了7个Prompt工程核心技巧，从基础语法到高级思维链，全面拆解。",
            "分析了1000组爆款AI绘画作品的Prompt，总结出高效Prompt的共通特征。",
            "这期讲Prompt设计中的3个致命错误和对应的解决方案。",
            "从认知心理学角度解析为什么某些Prompt效果好，教你举一反三。",
            "Prompt=咒语？No！这是一门需要系统学习的技术。这期建立完整知识框架。",
        ],
        "comments": [
            "这个框架太实用了，出图率肉眼可见地提升",
            "学习了！之前一直觉得AI画画靠运气，原来是方法不对",
            "开头那句'Prompt是思维而非咒语'说得太好了",
            "已截图保存，新手必备",
            "UP主的分析能力太强了，每个细节都讲透了",
        ],
    },
    "ai_tool_review": {
        "cn": "AI工具评测/对比",
        "sources": ["bilibili", "douyin", "xiaohongshu"],
        "titles": [
            "2026年最全AI工具盘点：这20个工具让你效率翻10倍",
            "GPT-5 vs Claude 4 vs Gemini 3：三大旗舰模型终极对决",
            "我测了50个AI工具，只有这7个值得付费",
            "国产AI工具爆发年：这10款完全不输海外产品",
            "AI工具订阅费一年花了3万，告诉你哪些钱该花哪些是智商税",
        ],
        "descriptions": [
            "整理了2026年最值得关注的20个AI工具，涵盖写作/绘画/视频/编程/办公五大类。",
            "用统一测试集对GPT-5、Claude 4和Gemini 3做了多维度评测。",
            "实测了50+款AI工具，从免费到付费全覆盖，告诉你哪些真正好用。",
            "国产AI过去一年的进步速度让人惊叹，这10款工具可以平替很多海外产品。",
            "一年花了3万订阅各种AI工具，这期直接给出省钱的购买建议。",
        ],
        "comments": [
            "这个对比太全面了，收藏了",
            "省流：前3个工具都是免费且超好用",
            "UP主的测评风格很客观，不恰饭好评",
            "你说的第7个工具我刚买了，确实物超所值",
            "这期的信息密度太高了，建议0.75倍速观看",
        ],
    },
    "ai_monetization": {
        "cn": "AI变现/副业教程",
        "sources": ["douyin", "xiaohongshu", "bilibili"],
        "titles": [
            "AI绘画接单月入5000+的完整攻略，适合副业小白",
            "我用AI做短视频带货，月佣金突破10万的真实复盘",
            "AI工具创业指南：一个人+AI，就是一家公司",
            "大学生用AI做自媒体，3个月涨粉5万的实操经验",
            "打工人副业选AI赛道，为什么我说这是最好的时机",
        ],
        "descriptions": [
            "分享我从零开始用AI绘画接单的全过程，包括平台选择、定价策略、客户沟通技巧。",
            "复盘我用AI工具做短视频带货的真实数据，以及可复用的选品和内容策略。",
            "这期讲AI时代个人创业的思维模型：如何最大化AI杠杆效应。",
            "大学生用AI做自媒体的完整历程：内容定位→AI辅助创作→数据分析→变现闭环。",
            "解析为什么AI赛道是当下副业入门门槛最低、天花板最高的方向。",
        ],
        "comments": [
            "看完了！决定明天开始行动",
            "这期太燃了，开头'AI不是取代你而是放大你'说得热血沸腾",
            "求问版主，哪种AI工具接单最赚钱？",
            "已实践第二周，确实有效果，感谢分享",
            "结尾那段'行动胜于完美'说得太对了",
        ],
    },
    "ai_creative_short": {
        "cn": "AI创意短片/故事",
        "sources": ["bilibili", "douyin"],
        "titles": [
            "我用AI生成了一支赛博朋克末日短片，每一帧都是壁纸",
            "AI复原了100年前的老北京影像，弹幕直接泪目",
            "用AI把《三体》概念图做成了短片，大刘看到都说像",
            "我让AI画出了自己做的梦，结果让我头皮发麻",
            "AI+真人拍摄混合作品：虚实之间的边界在哪里？",
        ],
        "descriptions": [
            "这支赛博朋克短片用了Midjourney+Kling+剪映，从概念到成片花了2周。",
            "用AI复原了100年前的老照片画面并让它们动起来，效果让人感动落泪。",
            "把《三体》中的名场面用AI可视化，黑暗森林、水滴、二向箔全部还原。",
            "这期尝试了一个新形式：AI+真人实拍混剪，探索虚实结合的艺术可能。",
            "用AI画出了自己描述过的梦境，然后再用视频生成工具把它们变成了动态画面。",
        ],
        "comments": [
            "开头3秒那个世界末日场景直接头皮发麻，太震撼了",
            "用AI复原历史画面这个点子太好了，期待更多作品",
            "水滴那段的粒子特效是怎么做的？太科幻了",
            "BGM和画面的节奏配合得太完美了",
            "这才是AI的正确用法！艺术+技术的完美结合",
        ],
    },
}

PLATFORM_MAP = {
    "bilibili": "bilibili",
    "douyin": "douyin",
    "xiaohongshu": "xiaohongshu",
}


def _make_dedupe_key(source_id: str, text: str) -> str:
    raw = f"{source_id}{text[:120]}"
    return hashlib.md5(raw.encode()).hexdigest()[:32]


async def main() -> None:
    from signal_miner.db import init_db
    from signal_miner.pipeline.runner import ingest_feedback
    from signal_miner.settings import AppSettings

    settings = AppSettings()
    await init_db(settings.database_url)

    total = 0
    for cat_key, cat in CATEGORIES.items():
        titles = cat["titles"]
        descs = cat["descriptions"]
        comments_list = cat["comments"]
        sources = cat["sources"]
        cnt = len(titles)

        for idx in range(cnt):
            source_type = random.choice(sources)
            platform = source_type.replace("video_", "")
            subject = titles[idx]
            description = descs[idx]

            # Pick 3-5 comments randomly
            comment_count = random.randint(3, 5)
            selected_comments = random.sample(comments_list, min(comment_count, len(comments_list)))

            text = f"""[视频简介] {description}

[创作者自述] 这期视频做了一周，从选题到后期全是自己一个人肝的。点赞过{random.choice([500, 1000, 2000, 5000, 10000])}的话明天出下期教程！

[热门评论]
""" + "\n".join(f"  · {c}" for c in selected_comments)

            views = random.randint(100_000, 5_000_000)
            likes = int(views * random.uniform(0.02, 0.08))

            source_id = f"{source_type}_sample_{cat_key}_{idx:02d}"
            dedupe_key = _make_dedupe_key(source_id, text)

            data = {
                "source_type": source_type,
                "source_id": source_id,
                "dedupe_key": dedupe_key,
                "author": {
                    "name": f"AI创作者_{cat_key}_{idx}",
                    "segment": cat["cn"],
                },
                "content": {
                    "subject": subject,
                    "text": text,
                },
                "context": {
                    "video_url": f"https://www.{source_type}.com/video/sample_{cat_key}_{idx:03d}",
                    "views": views,
                    "likes": likes,
                    "platform": platform,
                },
            }

            fb_id = await ingest_feedback(data, pipeline_profile="aigc_video")
            total += 1
            print(f"[{total:02d}] {fb_id} | {source_type:12s} | {cat['cn']:12s} | {views//10000:>3d}万播放 | {likes//10000:>2d}万赞")

    print(f"\n✅ 导入完成: {total} 条 AIGC 视频样本 (pipeline_profile='aigc_video')")


if __name__ == "__main__":
    asyncio.run(main())
