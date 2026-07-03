"""JSON Schema + descriptions for agent/MCP tools (mirrors ai-layer definitions)."""

MOVIE_LIST_TYPES = [
    "phim-bo",
    "phim-le",
    "tv-shows",
    "hoat-hinh",
    "phim-vietsub",
    "phim-thuyet-minh",
    "phim-long-tieng",
]

_PROVIDER_PARAM = {
    "type": "string",
    "enum": ["kkphim", "ophim"],
    "default": "kkphim",
    "description": "Nguồn phim: kkphim (phimapi.com) hoặc ophim (ophim1.com). Mặc định kkphim.",
}

_PAGE_PARAM = {"type": "integer", "default": 1, "minimum": 1}
_LIMIT_PARAM = {"type": "integer", "default": 10, "minimum": 1, "maximum": 24}

_LIST_FILTER_PROPS = {
    "category": {"type": "string", "description": "Slug thể loại lọc, vd hanh-dong"},
    "country": {"type": "string", "description": "Slug quốc gia lọc, vd han-quoc"},
    "year": {"type": "integer", "description": "Năm phát hành, vd 2024"},
    "sort_lang": {
        "type": "string",
        "enum": ["vietsub", "thuyet-minh", "long-tieng"],
        "description": "Lọc theo ngôn ngữ phụ đề",
    },
    "sort_field": {
        "type": "string",
        "enum": ["modified.time", "_id", "year"],
        "description": "Trường sắp xếp",
    },
    "sort_type": {"type": "string", "enum": ["desc", "asc"], "description": "Chiều sắp xếp"},
}

YOUTUBE_TOOL_SPECS: list[dict] = [
    {
        "name": "youtube_search",
        "description": "Tìm video YouTube theo từ khóa. DÙNG max_results=5, chọn đúng 3 video view cao nhất rồi gọi comments_batch + transcript_batch. KHÔNG gọi search lại. KHÔNG liệt kê video trong câu trả lời.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "max_results": {"type": "integer", "default": 5, "maximum": 5},
                "sort": {
                    "type": "string",
                    "enum": ["relevance", "upload_date", "view_count", "rating"],
                    "default": "relevance",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "youtube_get_by_topic",
        "description": "Lấy video theo chủ đề từ kênh YouTube chính thức. DÙNG KHI: user muốn xem video theo thể loại cụ thể. CHỦ ĐỀ HỖ TRỢ: music, gaming, news, sports, tech, beauty, food, travel.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["music", "gaming", "news", "sports", "tech", "beauty", "food", "travel"],
                },
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "youtube_get_shorts",
        "description": "Lấy danh sách YouTube Shorts đang thịnh hành. DÙNG KHI: user hỏi về Shorts hoặc video ngắn.",
        "parameters": {
            "type": "object",
            "properties": {"max_results": {"type": "integer", "default": 20, "maximum": 50}},
        },
    },
    {
        "name": "youtube_get_live",
        "description": "Lấy danh sách video đang live stream trên YouTube. DÙNG KHI: user hỏi về livestream đang diễn ra. Có thể lọc theo từ khóa tùy chọn.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa lọc (tùy chọn)", "default": ""},
                "max_results": {"type": "integer", "default": 20, "maximum": 50},
            },
        },
    },
    {
        "name": "youtube_get_by_region",
        "description": "Lấy video phổ biến theo khu vực địa lý cụ thể. DÙNG KHI: user muốn xem nội dung từ một quốc gia cụ thể. VÍ DỤ: gl=VN hl=vi query=Hà Nội để lấy video về Hà Nội.",
        "parameters": {
            "type": "object",
            "properties": {
                "gl": {"type": "string", "description": "Mã quốc gia (VN, JP, US...)"},
                "hl": {"type": "string", "description": "Mã ngôn ngữ (vi, ja, en...)", "default": "vi"},
                "query": {"type": "string", "description": "Từ khóa tìm kiếm theo ngôn ngữ địa phương"},
                "max_results": {"type": "integer", "default": 20, "maximum": 100},
            },
            "required": ["gl", "query"],
        },
    },
    {
        "name": "youtube_get_detail",
        "description": "Lấy thông tin chi tiết video: title, channel, views, description, thời lượng. YÊU CẦU: phải có video_id trước — gọi youtube_search nếu chưa có.",
        "parameters": {
            "type": "object",
            "properties": {"video_id": {"type": "string", "description": "YouTube video ID (vd: dQw4w9WgXcQ)"}},
            "required": ["video_id"],
        },
    },
    {
        "name": "youtube_get_comments",
        "description": "Lấy bình luận cho MỘT video YouTube. YÊU CẦU: phải có video_id. ƯU TIÊN dùng youtube_get_comments_batch khi muốn phân tích nhận xét — tool đơn lẻ này dễ bị rỗng nếu video đó khoá comment.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
                "max_comments": {"type": "integer", "default": 20, "maximum": 20},
                "sort": {"type": "string", "enum": ["newest", "top"], "default": "newest"},
            },
            "required": ["video_id"],
        },
    },
    {
        "name": "youtube_get_comments_batch",
        "description": "Lấy bình luận của NHIỀU video YouTube song song và gộp lại — CÁCH NÊN DÙNG để phân tích nhận xét cộng đồng. YÊU CẦU: mảng video_ids (chọn 3-5 video view CAO NHẤT từ youtube_search). Video bị khoá/0 comment sẽ tự bị bỏ qua, lấy comment từ các video còn lại — tránh được lỗi 'không có nhận xét' khi video top bị tắt comment. TRẢ VỀ: videos_with_comments, videos_skipped, total_comments, results[]. Chỉ cần gọi 1 lần với 3-5 id.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 video_id, ưu tiên view cao nhất",
                },
                "max_per_video": {"type": "integer", "default": 20, "maximum": 30},
                "sort": {"type": "string", "enum": ["top", "newest"], "default": "top"},
            },
            "required": ["video_ids"],
        },
    },
    {
        "name": "youtube_get_transcript",
        "description": "Lấy transcript (phụ đề/lời thoại) của một video YouTube. DÙNG KHI: cần phân tích nội dung video (reviewer nói gì) thay vì chỉ comment. Kết hợp với youtube_get_comments_batch để có cả nội dung lẫn phản ứng cộng đồng. TRẢ VỀ: text transcript, language, available (False nếu video không có caption). LƯU Ý: ~60-70% video có caption. Nếu available=False, bỏ qua và dùng comment.",
        "parameters": {
            "type": "object",
            "properties": {"video_id": {"type": "string", "description": "YouTube video ID"}},
            "required": ["video_id"],
        },
    },
    {
        "name": "youtube_get_transcript_batch",
        "description": "Lấy transcript của NHIỀU video YouTube song song — hiệu quả hơn gọi từng cái. DÙNG KHI: muốn phân tích nội dung nhiều video cùng lúc (kết hợp comments + transcript). TRẢ VỀ: dict {video_id: transcript_data}. Video không có caption → null. Tối đa 8 video_ids.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 video_id cần lấy transcript",
                }
            },
            "required": ["video_ids"],
        },
    },
    {
        "name": "youtube_get_channel_info",
        "description": "Lấy thông tin kênh YouTube: tên, subscriber, mô tả, avatar. YÊU CẦU: phải có channel_id (dạng UC...) hoặc @handle.",
        "parameters": {
            "type": "object",
            "properties": {"channel_id": {"type": "string", "description": "Channel ID (UCxxxx) hoặc @handle"}},
            "required": ["channel_id"],
        },
    },
    {
        "name": "youtube_get_channel_videos",
        "description": "Lấy danh sách video mới nhất của một kênh YouTube. YÊU CẦU: phải có channel_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["channel_id"],
        },
    },
    {
        "name": "youtube_get_channel_playlists",
        "description": "Lấy danh sách playlist của một kênh YouTube. YÊU CẦU: phải có channel_id.",
        "parameters": {"type": "object", "properties": {"channel_id": {"type": "string"}}, "required": ["channel_id"]},
    },
    {
        "name": "youtube_get_playlist_videos",
        "description": "Lấy danh sách video trong một playlist YouTube. YÊU CẦU: phải có playlist_id (dạng PL...). Có thể lấy từ youtube_get_channel_playlists.",
        "parameters": {
            "type": "object",
            "properties": {
                "playlist_id": {"type": "string", "description": "Playlist ID (PLxxxx)"},
                "max_results": {"type": "integer", "default": 30, "maximum": 50},
            },
            "required": ["playlist_id"],
        },
    },
]

TIKTOK_TOOL_SPECS: list[dict] = [
    {
        "name": "tiktok_search",
        "description": "Tìm kiếm video TikTok theo từ khóa. DÙNG KHI: cần tìm video review, xu hướng, nội dung về sản phẩm/chủ đề trên TikTok. TRẢ VỀ: danh sách video kèm thông tin tác giả, stats, description. KHÔNG DÙNG khi user đã paste link TikTok — gọi tiktok_video_info trực tiếp.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "cursor": {"type": "integer", "default": 0},
                "sort_by": {"type": "string", "enum": ["most-liked", "most-viewed", "most-recent", "most-relevant"]},
                "date_posted": {"type": "string", "enum": ["today", "this-week", "this-month", "this-year"]},
                "region": {"type": "string", "description": "Mã quốc gia proxy (US, VN...)"},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "tiktok_video_info",
        "description": "Lấy thông tin chi tiết của một video TikTok: views, likes, comments, description, tác giả. YÊU CẦU: phải có URL đầy đủ của video TikTok.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "TikTok video URL đầy đủ"}},
            "required": ["url"],
        },
    },
    {
        "name": "tiktok_comments",
        "description": "Lấy bình luận của người xem cho một video TikTok. YÊU CẦU: aweme_id (video ID số, lấy từ tiktok_search hoặc tiktok_video_info). DÙNG KHI: cần ý kiến thực tế từ người dùng về sản phẩm/chủ đề trong video.",
        "parameters": {
            "type": "object",
            "properties": {
                "aweme_id": {"type": "string", "description": "TikTok video ID (số)"},
                "cursor": {"type": "integer", "default": 0},
                "count": {"type": "integer", "default": 20, "maximum": 50},
            },
            "required": ["aweme_id"],
        },
    },
    {
        "name": "tiktok_profile",
        "description": "Lấy thông tin profile TikTok: follower count, following, bio, số video. DÙNG KHI: user muốn nghiên cứu một creator/influencer cụ thể. YÊU CẦU: handle (không cần @).",
        "parameters": {
            "type": "object",
            "properties": {"handle": {"type": "string", "description": "TikTok handle (không cần @)"}},
            "required": ["handle"],
        },
    },
    {
        "name": "tiktok_transcript",
        "description": "Lấy transcript (phụ đề/lời thoại) của một video TikTok qua TikHub. DÙNG KHI: cần phân tích nội dung creator nói trong video, kết hợp với tiktok_comments. YÊU CẦU: aweme_id (video ID số). TRẢ VỀ: text, language, available (False nếu video không có caption).",
        "parameters": {
            "type": "object",
            "properties": {"aweme_id": {"type": "string", "description": "TikTok video ID (số)"}},
            "required": ["aweme_id"],
        },
    },
]

MOVIE_TOOL_SPECS: list[dict] = [
    {
        "name": "movie_search",
        "description": (
            "Tìm phim theo từ khóa. kkphim: chỉ tên phim; ophim: tên phim + diễn viên. "
            "DÙNG KHI user hỏi tên phim, diễn viên, hoặc muốn tìm phim cụ thể. "
            "TRẢ VỀ danh sách phim kèm slug — dùng movie_get_detail để lấy chi tiết."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khóa tìm kiếm"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "movie_get_detail",
        "description": (
            "Lấy chi tiết phim: mô tả, thể loại, quốc gia, tập phim, link xem. "
            "YÊU CẦU slug từ movie_search hoặc danh sách phim."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug phim, vd avatar-2"},
                "provider": _PROVIDER_PARAM,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "movie_list_new",
        "description": "Lấy danh sách phim mới cập nhật. DÙNG KHI user hỏi phim mới, phim vừa ra.",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
            },
        },
    },
    {
        "name": "movie_list_by_type",
        "description": (
            "Lấy danh sách phim theo loại. "
            "type: phim-bo | phim-le | tv-shows | hoat-hinh | phim-vietsub | phim-thuyet-minh | phim-long-tieng. "
            "kkphim hỗ trợ filter nâng cao; ophim chỉ page + limit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": MOVIE_LIST_TYPES, "description": "Loại phim"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["type"],
        },
    },
    {
        "name": "movie_list_by_genre",
        "description": "Lấy phim theo thể loại (slug). DÙNG KHI user hỏi phim hành động, kinh dị, tình cảm…",
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug thể loại, vd hanh-dong"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "movie_list_by_country",
        "description": "Lấy phim theo quốc gia (slug). DÙNG KHI user hỏi phim Hàn, Mỹ, Trung…",
        "parameters": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug quốc gia, vd han-quoc"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["slug"],
        },
    },
    {
        "name": "movie_list_by_year",
        "description": "Lấy phim theo năm phát hành. DÙNG KHI user hỏi phim năm 2024, 2023…",
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Năm 4 chữ số, vd 2024"},
                "provider": _PROVIDER_PARAM,
                "page": _PAGE_PARAM,
                "limit": _LIMIT_PARAM,
                **_LIST_FILTER_PROPS,
            },
            "required": ["year"],
        },
    },
    {
        "name": "movie_get_metadata",
        "description": "Lấy metadata thể loại hoặc quốc gia (slug dùng cho filter/list). kind: genres | countries.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["genres", "countries"]},
                "provider": _PROVIDER_PARAM,
            },
            "required": ["kind"],
        },
    },
]
