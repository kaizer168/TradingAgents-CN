#!/usr/bin/env python3
"""
Add ANTHROPICGLM provider and glm-5 model configuration

This script adds:
1. ANTHROPICGLM provider (using Anthropic API compatible endpoint)
2. glm-5 model configuration

ANTHROPICGLM uses Anthropic API format with base URL: https://open.bigmodel.cn/api/anthropic
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ANTHROPICGLM Provider Configuration
ANTHROPICGLM_PROVIDER = {
    "name": "anthropicglm",
    "display_name": "ANTHROPICGLM",
    "description": "智谱AI Anthropic API 兼容模式 - 使用 Anthropic API 格式调用 GLM 模型",
    "website": "https://open.bigmodel.cn/",
    "api_doc_url": "https://open.bigmodel.cn/dev/api",
    "is_active": True,
    "supported_features": ["tool_calling", "long_context", "reasoning", "fast_response"],
    "default_base_url": "https://open.bigmodel.cn/api/anthropic",
    "api_key": os.getenv("ANTHROPICGLM_API_KEY", ""),
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}

# GLM-5 Model Configuration for ANTHROPICGLM provider
GLM5_MODEL = {
    "provider": "anthropicglm",
    "model_name": "glm-5",
    "model_display_name": "GLM-5 (Anthropic API)",
    "api_key": os.getenv("ANTHROPICGLM_API_KEY", ""),
    "api_base": "https://open.bigmodel.cn/api/anthropic",
    "max_tokens": 4000,
    "temperature": 0.7,
    "timeout": 180,
    "retry_times": 3,
    "enabled": True,
    "capability_level": 5,
    "suitable_roles": ["quick_analysis", "deep_analysis", "both"],
    "features": ["tool_calling", "long_context", "reasoning", "fast_response", "cost_effective"],
    "recommended_depths": ["快速", "基础", "标准", "深度", "全面"],
    "performance_metrics": {"speed": 5, "cost": 4, "quality": 5},
    "description": "GLM-5 via Anthropic API - 新一代旗舰模型，强大推理能力和工具调用支持",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}


async def add_anthropicglm_provider():
    """Add or update ANTHROPICGLM provider in database"""

    # Connect to MongoDB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGODB_DATABASE", "tradingagents")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[mongo_db]

    try:
        # ========== Step 1: Add/Update ANTHROPICGLM Provider ==========
        providers_collection = db.llm_providers

        existing_provider = await providers_collection.find_one({"name": "anthropicglm"})

        if existing_provider:
            # Update existing provider
            update_data = {
                "is_active": True,
                "default_base_url": ANTHROPICGLM_PROVIDER["default_base_url"],
                "supported_features": ANTHROPICGLM_PROVIDER["supported_features"],
                "description": ANTHROPICGLM_PROVIDER["description"],
                "updated_at": datetime.utcnow()
            }
            # Only update API key if it's set in environment
            if ANTHROPICGLM_PROVIDER["api_key"]:
                update_data["api_key"] = ANTHROPICGLM_PROVIDER["api_key"]

            await providers_collection.update_one(
                {"name": "anthropicglm"},
                {"$set": update_data}
            )
            print(f"✅ ANTHROPICGLM provider updated (ID: {existing_provider['_id']})")
        else:
            # Create new provider
            result = await providers_collection.insert_one(ANTHROPICGLM_PROVIDER)
            print(f"✅ ANTHROPICGLM provider created (ID: {result.inserted_id})")

        # ========== Step 2: Add GLM-5 Model to system_configs ==========
        configs_collection = db.system_configs

        # Get the active system config
        config = await configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

        if not config:
            print("❌ No active system config found. Please create one first via Web UI.")
            return False

        existing_models = config.get("llm_configs", [])
        existing_model_names = {m.get("model_name") for m in existing_models}
        existing_model_providers = {(m.get("model_name"), m.get("provider")) for m in existing_models}

        model_key = (GLM5_MODEL["model_name"], GLM5_MODEL["provider"])

        if model_key in existing_model_providers:
            # Update existing model
            update_fields = {
                "llm_configs.$.enabled": True,
                "llm_configs.$.api_base": GLM5_MODEL["api_base"],
                "llm_configs.$.max_tokens": GLM5_MODEL["max_tokens"],
                "llm_configs.$.temperature": GLM5_MODEL["temperature"],
                "llm_configs.$.timeout": GLM5_MODEL["timeout"],
                "llm_configs.$.capability_level": GLM5_MODEL["capability_level"],
                "llm_configs.$.features": GLM5_MODEL["features"],
                "llm_configs.$.description": GLM5_MODEL["description"],
                "llm_configs.$.updated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            # Only update API key if it's set in environment
            if GLM5_MODEL["api_key"]:
                update_fields["llm_configs.$.api_key"] = GLM5_MODEL["api_key"]

            await configs_collection.update_one(
                {"_id": config["_id"], "llm_configs.model_name": GLM5_MODEL["model_name"], "llm_configs.provider": GLM5_MODEL["provider"]},
                {"$set": update_fields}
            )
            print(f"✅ GLM-5 model (anthropicglm) updated in system config")
        else:
            # Add new model
            result = await configs_collection.update_one(
                {"_id": config["_id"]},
                {
                    "$push": {"llm_configs": GLM5_MODEL},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            if result.modified_count > 0:
                print(f"✅ GLM-5 model (anthropicglm) added to system config")
            else:
                print(f"❌ Failed to add GLM-5 model")
                return False

        # ========== Step 3: Verify Configuration ==========
        print("\n" + "=" * 60)
        print("📋 Configuration Summary:")
        print("=" * 60)
        print(f"  Provider:     anthropicglm")
        print(f"  Model:        glm-5")
        print(f"  Base URL:     {ANTHROPICGLM_PROVIDER['default_base_url']}")
        print(f"  API Key:      {'✅ Set' if ANTHROPICGLM_PROVIDER['api_key'] else '❌ Not set'}")
        print(f"  Capability:   Level {GLM5_MODEL['capability_level']} (Flagship)")
        print(f"  Features:     {', '.join(GLM5_MODEL['features'])}")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


def print_usage():
    """Print usage instructions"""
    print("\n" + "=" * 60)
    print("📝 Usage Instructions:")
    print("=" * 60)
    print("""
1. Set API Key (choose one method):

   Method A - Environment Variable:
   ```bash
   export ANTHROPICGLM_API_KEY="your_api_key_here"
   ```

   Method B - .env file:
   ```
   ANTHROPICGLM_API_KEY=your_api_key_here
   ```

   Method C - Web UI:
   Settings -> LLM Providers -> ANTHROPICGLM -> Configure API Key

2. Run this script:
   ```bash
   python scripts/add_anthropicglm_model_glm5.py
   ```

3. Restart the backend service

4. Refresh the frontend and select ANTHROPICGLM as provider

5. Select glm-5 as the model for quick/deep thinking
""")


if __name__ == "__main__":
    print("🔧 Adding ANTHROPICGLM provider and GLM-5 model...")
    print("=" * 60)

    success = asyncio.run(add_anthropicglm_provider())

    if success:
        print("\n✅ Configuration completed successfully!")
        print_usage()
    else:
        print("\n❌ Configuration failed. Please check the errors above.")
