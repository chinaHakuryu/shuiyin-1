python
import os
import subprocess
import sys
import traceback
import json

# 平台列表
PLATFORMS = {
    "douyin": "抖音精选",
    "kuaishou": "快手精选",
    "baijiahao": "百家号精选",
    "weibo": "微博",
    "meitan": "美团精选",
    "duoduo": "多多精选",
    "zfb": "支付宝精选",
    "weishi": "腾讯微视精选",
    "toutiao": "头条精选",
    "ppx": "皮皮虾精选",
    "aiqiyi": "爱奇艺精选",
    "xiaohongshu": "小红书精选",
    "wechat": "视频号精选",
    "douyin2": "抖音瞎选",
    "dewu": "得物精选"
}

def load_config():
    """加载配置文件"""
    config_path = "watermark_config.json"
    default_config = {
        "global": {
            "position_mode": "coordinates",
            "size": {
                "scale": 0.10
            }
        },
        "platforms": {}
    }
    
    # 为所有平台创建默认配置
    for platform in PLATFORMS.keys():
        default_config["platforms"][platform] = {
            "position_mode": "coordinates",
            "coordinates": {
                "x": 100,
                "y": 200
            },
            "margins": {
                "right_margin": 50,
                "bottom_margin": 50
            }
        }
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # 如果配置文件是旧格式，转换为新格式
            if "position_mode" in config and "platforms" not in config:
                print("检测到旧版配置文件，正在转换为新格式...")
                new_config = default_config.copy()
                new_config["global"] = {
                    "position_mode": config.get("position_mode", "coordinates"),
                    "size": config.get("size", {"scale": 0.10})
                }
                
                # 为所有平台设置相同的配置
                for platform in PLATFORMS.keys():
                    new_config["platforms"][platform] = {
                        "position_mode": config.get("position_mode", "coordinates"),
                        "coordinates": config.get("coordinates", {"x": 100, "y": 200}),
                        "margins": config.get("margins", {"right_margin": 50, "bottom_margin": 50})
                    }
                
                # 保存新格式的配置
                with open(config_path, 'w', encoding='utf-8') as f_out:
                    json.dump(new_config, f_out, indent=4, ensure_ascii=False)
                
                return new_config
                
            return config
    except:
        print("配置文件不存在或格式错误，使用默认配置")
        return default_config

def get_video_info(video_path):
    """获取视频信息的更健壮方法"""
    try:
        # 分别获取视频信息
        cmd_width_height = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path
        ]
        
        cmd_bitrate = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate', '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        
        cmd_codec = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        
        cmd_pix_fmt = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=pix_fmt', '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        
        # 执行命令
        result_wh = subprocess.run(cmd_width_height, capture_output=True, text=True, timeout=10)
        result_br = subprocess.run(cmd_bitrate, capture_output=True, text=True, timeout=10)
        result_codec = subprocess.run(cmd_codec, capture_output=True, text=True, timeout=10)
        result_pix = subprocess.run(cmd_pix_fmt, capture_output=True, text=True, timeout=10)
        
        # 解析结果
        width, height = 0, 0
        if result_wh.returncode == 0 and result_wh.stdout.strip():
            wh_parts = result_wh.stdout.strip().split(',')
            if len(wh_parts) >= 2:
                width, height = int(wh_parts[0]), int(wh_parts[1])
        
        bitrate = None
        if result_br.returncode == 0 and result_br.stdout.strip():
            bitrate = int(result_br.stdout.strip())
        
        codec = 'h264'
        if result_codec.returncode == 0 and result_codec.stdout.strip():
            codec = result_codec.stdout.strip()
        
        pix_fmt = 'yuv420p'
        if result_pix.returncode == 0 and result_pix.stdout.strip():
            pix_fmt = result_pix.stdout.strip()
        
        return {
            'width': width,
            'height': height,
            'bitrate': bitrate,
            'codec': codec,
            'pix_fmt': pix_fmt
        }
        
    except Exception as e:
        print(f"获取视频信息失败: {str(e)}")
        return {'width': 1920, 'height': 1080, 'bitrate': None, 'codec': 'h264', 'pix_fmt': 'yuv420p'}

def get_image_info(image_path):
    """获取图片信息的正确方法 - 使用FFprobe而不是PIL"""
    try:
        # 使用FFprobe获取图片信息
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'csv=p=0', image_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            if len(parts) >= 2:
                return {
                    'width': int(parts[0]),
                    'height': int(parts[1])
                }
        
        # 如果FFprobe失败，使用默认值
        return {'width': 300, 'height': 100}
        
    except Exception as e:
        print(f"获取图片信息失败: {str(e)}")
        return {'width': 300, 'height': 100}

def add_watermark_with_ffmpeg(input_video_path, watermark_image_path, output_video_path, 
                             platform_config, global_config):
    """
    使用FFmpeg为视频添加水印（支持精确坐标，自动适应不同分辨率）
    """
    
    print(f"正在处理: {os.path.basename(input_video_path)} -> {os.path.basename(output_video_path)}")
    
    try:
        # 获取视频信息
        video_info = get_video_info(input_video_path)
        video_width = video_info['width']
        video_height = video_info['height']
        video_bitrate = video_info['bitrate']
        video_codec = video_info['codec']
        video_pix_fmt = video_info['pix_fmt']
        
        print(f"视频尺寸: {video_width}x{video_height}, 像素格式: {video_pix_fmt}")
        print(f"视频编码: {video_codec}, 比特率: {video_bitrate} bps" if video_bitrate else f"视频编码: {video_codec}")
        
        # 获取水印图片信息
        watermark_info = get_image_info(watermark_image_path)
        watermark_width = watermark_info['width']
        watermark_height = watermark_info['height']
        print(f"水印原始尺寸: {watermark_width}x{watermark_height}")
        print(f"水印宽高比: {watermark_width/watermark_height:.2f}:1")
        
        # 使用全局缩放比例
        scale = global_config['size']['scale']
        
        # 计算水印大小 - 保持原始宽高比
        new_height = int(video_height * scale)
        # 根据原始宽高比计算新宽度
        aspect_ratio = watermark_width / watermark_height
        new_width = int(new_height * aspect_ratio)
        
        print(f"水印调整后尺寸: {new_width}x{new_height} (缩放比例: {scale*100}%)")
        print(f"调整后宽高比: {new_width/new_height:.2f}:1")
        
        # 计算水印位置 - 基于相对位置的比例
        position_mode = platform_config['position_mode']
        
        # 基准分辨率（假设配置是基于1080p设置的）
        base_width = 1920
        base_height = 1080
        
        if position_mode == 'coordinates':
            # 使用相对坐标（基于比例）
            base_x = platform_config['coordinates']['x']
            base_y = platform_config['coordinates']['y']
            
            # 计算相对比例 - 分别计算X和Y的比例
            x_ratio = base_x / base_width
            y_ratio = base_y / base_height
            
            # 根据当前视频分辨率计算实际坐标
            x = int(video_width * x_ratio)
            
            # 对于Y坐标，根据位置选择不同的计算方式
            if base_y < base_height * 0.3:  # 顶部区域
                y = int(video_height * y_ratio)
            elif base_y > base_height * 0.7:  # 底部区域
                from_bottom = base_height - base_y
                bottom_ratio = from_bottom / base_height
                y = video_height - int(video_height * bottom_ratio)
            else:  # 中间区域
                y = int(video_height * y_ratio)
            
            position_info = f"相对坐标: 原({base_x},{base_y})→新({x},{y})"
            
        else:
            # 使用相对边距
            base_right_margin = platform_config['margins']['right_margin']
            base_bottom_margin = platform_config['margins']['bottom_margin']
            
            # 计算相对比例
            right_ratio = base_right_margin / base_width
            bottom_ratio = base_bottom_margin / base_height
            
            # 根据当前视频分辨率计算实际边距
            right_margin = int(video_width * right_ratio)
            bottom_margin = int(video_height * bottom_ratio)
            
            x = video_width - new_width - right_margin
            y = video_height - new_height - bottom_margin
            
            position_info = f"相对边距: 右边距={right_margin}px, 底边距={bottom_margin}px"
        
        # 确保水印在视频范围内
        original_x, original_y = x, y
        
        if x < 0:
            x = 10
            print(f"⚠️  警告: X坐标从 {original_x} 调整到 {x}")
        if y < 0:
            y = 10
            print(f"⚠️  警告: Y坐标从 {original_y} 调整到 {y}")
        if x + new_width > video_width:
            x = video_width - new_width - 10
            print(f"⚠️  警告: X坐标从 {original_x} 调整到 {x}")
        if y + new_height > video_height:
            y = video_height - new_height - 10
            print(f"⚠️  警告: Y坐标从 {original_y} 调整到 {y}")
        
        print(f"水印位置: ({x}, {y})")
        print(position_info)
        
        # 显示调试信息
        print(f"基准分辨率: {base_width}x{base_height}")
        print(f"当前分辨率: {video_width}x{video_height}")
        print(f"缩放比例: X={video_width/base_width:.2f}, Y={video_height/base_height:.2f}")
        
        # 构建FFmpeg命令
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_video_path,
            '-i', watermark_image_path,
            '-filter_complex', 
            f"[1]scale={new_width}:{new_height}:force_original_aspect_ratio=decrease[wm];" +
            f"[0][wm]overlay={x}:{y}",
            '-c:v', 'libx264',
            '-preset', 'slow',
            '-crf', '18',
            '-profile:v', 'high',
            '-level', '4.1',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-c:a', 'copy',
            '-y',
            output_video_path
        ]
        
        # 如果知道原视频比特率，使用相似的比特率
        if video_bitrate:
            target_bitrate = int(video_bitrate * 1.1)
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', input_video_path,
                '-i', watermark_image_path,
                '-filter_complex', 
                f"[1]scale={new_width}:{new_height}:force_original_aspect_ratio=decrease[wm];" +
                f"[0][wm]overlay={x}:{y}",
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-b:v', f'{target_bitrate}',
                '-maxrate', f'{target_bitrate * 1.5}',
                '-bufsize', f'{target_bitrate * 2}',
                '-profile:v', 'high',
                '-level', '4.1',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-c:a', 'copy',
                '-y',
                output_video_path
            ]
        
        print("正在添加水印...")
        
        # 运行FFmpeg命令
        result = subprocess.run(
            ffmpeg_cmd, 
            capture_output=True, 
            text=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            output_size = os.path.getsize(output_video_path)
            input_size = os.path.getsize(input_video_path)
            size_ratio = output_size / input_size
            
            print(f"✅ 已完成: {os.path.basename(output_video_path)}")
            print(f"文件大小: 输入 {input_size/1024/1024:.2f}MB → 输出 {output_size/1024/1024:.2f}MB")
            print(f"大小比例: {size_ratio:.2%}")
            
            return True
        else:
            print(f"❌ FFmpeg处理失败，返回码: {result.returncode}")
            print(f"FFmpeg错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg处理超时")
        return False
    except Exception as e:
        print(f"❌ 处理视频时出错: {str(e)}")
        print(traceback.format_exc())
        return False

def select_platforms():
    """选择要处理的平台"""
    print("\n请选择要添加水印的平台:")
    print("0. 所有平台")
    
    platforms_list = list(PLATFORMS.items())
    for i, (key, name) in enumerate(platforms_list, 1):
        print(f"{i}. {name}")
    
    selected_platforms = []
    
    while True:
        try:
            choice = input("\n请输入平台编号 (多个编号用逗号分隔, 0表示所有平台): ").strip()
            
            if choice == "0":
                # 选择所有平台
                selected_platforms = list(PLATFORMS.keys())
                print("已选择所有平台")
                break
            
            choices = [c.strip() for c in choice.split(",")]
            valid_choices = []
            
            for c in choices:
                if not c:
                    continue
                    
                index = int(c) - 1
                if 0 <= index < len(platforms_list):
                    platform_key, platform_name = platforms_list[index]
                    valid_choices.append(platform_key)
                    print(f"已选择: {platform_name}")
                else:
                    print(f"无效的平台编号: {c}")
            
            if valid_choices:
                selected_platforms = valid_choices
                break
            else:
                print("没有选择任何有效平台，请重新选择")
                
        except ValueError:
            print("请输入有效的数字!")
        except Exception as e:
            print(f"选择平台时出错: {str(e)}")
    
    return selected_platforms

def batch_add_watermarks_ffmpeg():
    """使用FFmpeg批量为视频添加多个平台的水印"""
    
    # 加载配置
    config = load_config()
    global_config = config['global']
    
    print(f"使用全局缩放比例: {global_config['size']['scale']*100}%")
    
    # 选择要处理的平台
    selected_platforms = select_platforms()
    if not selected_platforms:
        print("没有选择任何平台，退出处理")
        input("按回车键退出...")
        return
    
    # 设置路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "input_video")
    watermarks_dir = os.path.join(base_dir, "watermarks")
    output_dir = os.path.join(base_dir, "output_videos")
    
    print("=" * 50)
    print("FFmpeg视频水印批量添加工具")
    print("=" * 50)
    
    # 检查输入目录是否存在
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录不存在: {input_dir}")
        print("请创建 input_video 文件夹并放入视频文件")
        input("按回车键退出...")
        return
    
    # 检查水印目录是否存在
    if not os.path.exists(watermarks_dir):
        print(f"❌ 水印目录不存在: {watermarks_dir}")
        print("请先运行 generate_watermarks.py 生成水印图片")
        input("按回车键退出...")
        return
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出目录: {output_dir}")
    
    # 获取输入视频
    input_videos = [f for f in os.listdir(input_dir) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.flv'))]
    
    if not input_videos:
        print("在 input_video 文件夹中没有找到视频文件!")
        print("支持的格式: .mp4, .mov, .avi, .mkv, .flv")
        input("按回车键退出...")
        return
    
    print(f"找到 {len(input_videos)} 个视频文件")
    
    # 处理每个视频
    success_count = 0
    fail_count = 0
    
    # 先测试一个视频和一个水印
    test_video = input_videos[0]
    test_platform = selected_platforms[0]
    
    print(f"\n先进行测试: {test_video} -> {test_platform}")
    
    input_video_path = os.path.join(input_dir, test_video)
    video_name = os.path.splitext(test_video)[0]
    watermark_path = os.path.join(watermarks_dir, f"{test_platform}.png")
    
    # 使用中文平台名称
    platform_name_chinese = PLATFORMS.get(test_platform, test_platform)
    output_filename = f"{video_name}_{platform_name_chinese}_带水印.mp4"
    output_path = os.path.join(output_dir, output_filename)
    
    if not os.path.exists(watermark_path):
        print(f"⚠️  警告: {platform_name_chinese} 的水印图片不存在")
        input("按回车键退出...")
        return
    
    # 获取平台配置
    platform_config = config['platforms'].get(test_platform, {
        "position_mode": "coordinates",
        "coordinates": {"x": 100, "y": 200},
        "margins": {"right_margin": 50, "bottom_margin": 50}
    })
    
    # 测试处理
    success = add_watermark_with_ffmpeg(
        input_video_path=input_video_path,
        watermark_image_path=watermark_path,
        output_video_path=output_path,
        platform_config=platform_config,
        global_config=global_config
    )
    
    if success:
        print("✅ 测试成功! 开始处理所有视频...")
        success_count += 1
        
        # 处理所有视频
        for video_file in input_videos:
            input_video_path = os.path.join(input_dir, video_file)
            video_name = os.path.splitext(video_file)[0]
            
            print(f"\n开始处理视频: {video_file}")
            
            # 为每个选中的平台添加水印
            for platform_key in selected_platforms:
                platform_name_chinese = PLATFORMS.get(platform_key, platform_key)
                watermark_path = os.path.join(watermarks_dir, f"{platform_key}.png")
                
                if not os.path.exists(watermark_path):
                    print(f"⚠️  警告: {platform_name_chinese} 的水印图片不存在")
                    fail_count += 1
                    continue
                
                # 使用中文平台名称
                output_filename = f"{video_name}_{platform_name_chinese}_带水印.mp4"
                output_path = os.path.join(output_dir, output_filename)
                
                print(f"\n正在为 {platform_name
