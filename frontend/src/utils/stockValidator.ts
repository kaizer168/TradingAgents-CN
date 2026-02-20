/**
 * 股票代码格式验证工具
 * 支持 A股、美股、港股、马股的代码格式验证
 */

export interface StockValidationResult {
  valid: boolean
  market?: 'A股' | '美股' | '港股' | '马股'
  message?: string
  normalizedCode?: string
}

/**
 * A股代码格式验证
 * 格式：6位数字
 * - 60xxxx: 上海主板
 * - 68xxxx: 科创板
 * - 00xxxx: 深圳主板
 * - 30xxxx: 创业板
 * - 43xxxx/83xxxx/87xxxx: 北交所
 */
export function validateAStock(code: string): StockValidationResult {
  // 移除空格和特殊字符
  const cleanCode = code.trim().replace(/[^0-9]/g, '')
  
  // 必须是6位数字
  if (!/^\d{6}$/.test(cleanCode)) {
    return {
      valid: false,
      message: 'A股代码必须是6位数字'
    }
  }
  
  // 验证前缀
  const prefix = cleanCode.substring(0, 2)
  const validPrefixes = ['60', '68', '00', '30', '43', '83', '87']
  
  if (!validPrefixes.includes(prefix)) {
    return {
      valid: false,
      message: 'A股代码前缀不正确（支持：60/68/00/30/43/83/87开头）'
    }
  }
  
  return {
    valid: true,
    market: 'A股',
    normalizedCode: cleanCode
  }
}

/**
 * 美股代码格式验证
 * 格式：1-5个大写字母
 * 示例：AAPL, MSFT, GOOGL, TSLA, BRK.B
 */
export function validateUSStock(code: string): StockValidationResult {
  // 移除空格，保留字母和点号
  const cleanCode = code.trim().toUpperCase().replace(/[^A-Z.]/g, '')
  
  // 基本格式：1-5个字母，可能包含一个点号
  if (!/^[A-Z]{1,5}(\.[A-Z])?$/.test(cleanCode)) {
    return {
      valid: false,
      message: '美股代码格式不正确（1-5个字母，如：AAPL、BRK.B）'
    }
  }
  
  // 不能全是点号
  if (cleanCode.replace(/\./g, '').length === 0) {
    return {
      valid: false,
      message: '美股代码不能为空'
    }
  }
  
  return {
    valid: true,
    market: '美股',
    normalizedCode: cleanCode
  }
}

/**
 * 港股代码格式验证
 * 格式：5位数字（前面可能有0）
 * 示例：00700（腾讯）、09988（阿里巴巴）、01810（小米）
 * 也支持不带前导0的格式：700、9988、1810
 */
export function validateHKStock(code: string): StockValidationResult {
  // 移除空格和特殊字符
  const cleanCode = code.trim().replace(/[^0-9]/g, '')

  // 必须是1-5位数字
  if (!/^\d{1,5}$/.test(cleanCode)) {
    return {
      valid: false,
      message: '港股代码必须是1-5位数字'
    }
  }

  // 转换为5位格式（补齐前导0）
  const normalizedCode = cleanCode.padStart(5, '0')

  return {
    valid: true,
    market: '港股',
    normalizedCode: normalizedCode
  }
}

/**
 * 马股代码格式验证
 * 格式：4位数字 + .KL 后缀
 * 示例：5347.KL（Tenaga）、1155.KL（Maybank）
 * 也支持不带后缀的格式：5347、1155
 */
export function validateMYStock(code: string): StockValidationResult {
  // 移除空格，转大写
  const cleanCode = code.trim().toUpperCase()

  // 检查是否已经是完整格式 (4位数字.KL)
  if (/^\d{4}\.KL$/.test(cleanCode)) {
    return {
      valid: true,
      market: '马股',
      normalizedCode: cleanCode
    }
  }

  // 检查是否是纯4位数字
  if (/^\d{4}$/.test(cleanCode)) {
    return {
      valid: true,
      market: '马股',
      normalizedCode: `${cleanCode}.KL`
    }
  }

  return {
    valid: false,
    message: '马股代码必须是4位数字（如：5347、1155）或带.KL后缀（如：5347.KL）'
  }
}

/**
 * 自动识别股票代码格式并验证
 * @param code 股票代码
 * @param marketHint 市场提示（可选），如果提供则优先验证该市场
 */
export function validateStockCode(
  code: string,
  marketHint?: 'A股' | '美股' | '港股' | '马股'
): StockValidationResult {
  if (!code || !code.trim()) {
    return {
      valid: false,
      message: '请输入股票代码'
    }
  }

  const trimmedCode = code.trim()

  // 如果提供了市场提示，优先验证该市场
  if (marketHint) {
    switch (marketHint) {
      case 'A股':
        return validateAStock(trimmedCode)
      case '美股':
        return validateUSStock(trimmedCode)
      case '港股':
        return validateHKStock(trimmedCode)
      case '马股':
        return validateMYStock(trimmedCode)
    }
  }

  // 自动识别：先判断是否带 .KL 后缀（马股）
  if (/^\d{4}\.KL$/i.test(trimmedCode)) {
    return validateMYStock(trimmedCode)
  }

  // 自动识别：判断是否全是数字
  const isNumeric = /^\d+$/.test(trimmedCode.replace(/[^0-9]/g, ''))

  if (isNumeric) {
    const cleanCode = trimmedCode.replace(/[^0-9]/g, '')

    // 6位数字 -> A股
    if (cleanCode.length === 6) {
      return validateAStock(cleanCode)
    }

    // 4位数字 -> 可能是马股或港股，默认识别为港股
    // 注意：马股通常带 .KL 后缀，不带后缀的4位数字优先识别为港股
    if (cleanCode.length >= 1 && cleanCode.length <= 5) {
      return validateHKStock(cleanCode)
    }

    return {
      valid: false,
      message: '数字代码长度不正确（A股6位，港股1-5位，马股4位.KL）'
    }
  }

  // 包含字母 -> 美股
  if (/[A-Za-z]/.test(trimmedCode)) {
    return validateUSStock(trimmedCode)
  }

  return {
    valid: false,
    message: '无法识别的股票代码格式'
  }
}

/**
 * 获取股票代码格式说明
 */
export function getStockCodeFormatHelp(market: 'A股' | '美股' | '港股' | '马股'): string {
  switch (market) {
    case 'A股':
      return '6位数字，如：000001（平安银行）、600519（贵州茅台）'
    case '美股':
      return '1-5个字母，如：AAPL（苹果）、TSLA（特斯拉）'
    case '港股':
      return '1-5位数字，如：700（腾讯）、9988（阿里巴巴）'
    case '马股':
      return '4位数字.KL，如：5347.KL（国家能源）、1155.KL（马来亚银行）'
    default:
      return ''
  }
}

/**
 * 获取股票代码示例
 */
export function getStockCodeExamples(market: 'A股' | '美股' | '港股' | '马股'): string[] {
  switch (market) {
    case 'A股':
      return ['000001', '600519', '000858', '300750']
    case '美股':
      return ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    case '港股':
      return ['00700', '09988', '01810', '03690']
    case '马股':
      return ['5347.KL', '1155.KL', '1066.KL', '7113.KL']
    default:
      return []
  }
}

/**
 * 格式化股票代码显示
 * @param code 原始代码
 * @param market 市场类型
 */
export function formatStockCode(code: string, market: 'A股' | '美股' | '港股' | '马股'): string {
  const validation = validateStockCode(code, market)
  return validation.normalizedCode || code
}

