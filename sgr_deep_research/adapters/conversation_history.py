"""
Conversation history extraction for Open-WebUI.
Extracts clean conversation history from messages, filtering out tool calls and intermediate steps.
"""
import html
import logging
import re

logger = logging.getLogger(__name__)


def extract_conversation_history(messages):
    """
    Extract conversation history, keeping only final assistant answers.
    
    Filters out intermediate tool calls, reasoning blocks, and HTML details
    from assistant messages, keeping only the final answer (text after last </details>).
    This significantly reduces context size while maintaining conversation continuity.
    
    Args:
        messages: List of messages from request
        
    Returns:
        list: Filtered conversation history with user-assistant pairs
    """
    logger.info("🔍 [HISTORY] Starting conversation history extraction")
    logger.info(f"🔍 [HISTORY] Total messages to process: {len(messages)}")
    
    history = []
    
    # Process messages sequentially, collecting user-assistant pairs
    i = 0
    while i < len(messages):
        msg = messages[i]
        
        # Process user message
        if msg.role == "user":
            logger.info(f"🔍 [HISTORY] [{i}] Found USER message: {msg.content[:100]}...")
            history.append({
                "role": "user",
                "content": msg.content
            })
            
            # Look for assistant response (skip tool_calls and tool messages)
            assistant_content = None
            j = i + 1
            logger.info(f"🔍 [HISTORY] Looking ahead for assistant response starting from index {j}")
            
            while j < len(messages):
                next_msg = messages[j]
                logger.info(f"🔍 [HISTORY]   [{j}] Checking message: role={next_msg.role}, has_content={bool(next_msg.content)}, content_length={len(next_msg.content) if next_msg.content else 0}")
                
                # Stop at next user message
                if next_msg.role == "user":
                    logger.info(f"🔍 [HISTORY]   [{j}] Hit next user message, stopping search")
                    break
                
                # Collect assistant content (skip tool_calls and tool messages)
                if next_msg.role == "assistant" and next_msg.content:
                    logger.info(f"🔍 [HISTORY] [{j}] Found ASSISTANT message, length: {len(next_msg.content)} chars")
                    logger.info(f"🔍 [HISTORY] First 200 chars: {next_msg.content[:200]}...")
                    
                    # Try to extract final answer using multiple strategies
                    final_answer = None
                    content = next_msg.content
                    
                    # Strategy 1: Look for ✓ marker (final answer marker)
                    checkmark_pos = content.rfind('✓')
                    if checkmark_pos != -1:
                        # Extract everything after ✓ marker
                        final_answer = content[checkmark_pos + 1:].strip()
                        logger.info(f"🔍 [HISTORY] Strategy 1 (✓ marker): Found at pos {checkmark_pos}, extracted {len(final_answer)} chars")
                    
                    # Strategy 2: Look for </details> tag and extract text after it
                    if not final_answer:
                        last_details_end = content.rfind('</details>')
                        if last_details_end != -1:
                            logger.info(f"🔍 [HISTORY] Strategy 2 (</details>): Found at pos {last_details_end}")
                            # Found details tags - extract everything after last one
                            potential_answer = content[last_details_end + len('</details>'):].strip()
                            logger.info(f"🔍 [HISTORY] Text after </details>: {potential_answer[:200]}...")
                            
                            # Clean and check that it's meaningful content
                            potential_answer = re.sub(r'^"undefined"\s*', '', potential_answer)
                            potential_answer = re.sub(r'"undefined"', '', potential_answer)
                            potential_answer = re.sub(r'^["\s&quot;]+', '', potential_answer)
                            
                            if len(potential_answer) > 20:  # Only if there's substantial content
                                final_answer = potential_answer
                                logger.info(f"🔍 [HISTORY] Strategy 2: Extracted {len(final_answer)} chars after cleanup")
                            else:
                                logger.info(f"🔍 [HISTORY] Strategy 2: Skipped (too short after cleanup: {len(potential_answer)} chars)")
                    
                    # Strategy 3: If message is short and has no details tags, use as-is
                    if not final_answer and len(content) < 500 and '<details' not in content:
                        final_answer = content
                        logger.info(f"🔍 [HISTORY] Strategy 3 (short message): Using as-is, {len(final_answer)} chars")
                    
                    # Strategy 4: For long messages, look for final answer by markers
                    # (may contain reasoning + final answer with markdown headers)
                    if not final_answer and len(content) > 5000:
                        logger.info(f"🔍 [HISTORY] Strategy 4: Analyzing long message ({len(content)} chars) for final answer")
                        
                        # Look for last markdown header (##) - usually the final answer
                        # Pattern: look for last level 2 header
                        markdown_headers = list(re.finditer(r'^##\s+[^\n]+', content, re.MULTILINE))
                        if markdown_headers:
                            # Take position of last header
                            last_header_pos = markdown_headers[-1].start()
                            potential_answer = content[last_header_pos:].strip()
                            logger.info(f"🔍 [HISTORY] Strategy 4: Found markdown header at pos {last_header_pos}, extracted {len(potential_answer)} chars")
                            
                            # Check that it's not just a header, but has content
                            if len(potential_answer) > 100:
                                final_answer = potential_answer
                                logger.info(f"🔍 [HISTORY] Strategy 4: Using content after last markdown header")
                            else:
                                logger.info(f"🔍 [HISTORY] Strategy 4: Content too short ({len(potential_answer)} chars)")
                        else:
                            logger.info(f"🔍 [HISTORY] Strategy 4: No markdown headers found, skipping long message")
                    
                    # Strategy 5: If still no answer and message is very long, skip
                    # (probably contains only tool execution details without final answer)
                    if not final_answer and len(content) > 5000:
                        logger.info(f"🔍 [HISTORY] Strategy 5: Skipping long message without final answer ({len(content)} chars)")
                        pass
                    
                    # Clean final answer
                    if final_answer:
                        # Remove HTML entities
                        final_answer = html.unescape(final_answer)
                        
                        # Remove &quot; entities that html.unescape might miss
                        final_answer = final_answer.replace('&quot;', '')
                        
                        # Remove extra quotes and spaces
                        final_answer = re.sub(r'^["\s]+|["\s]+$', '', final_answer)
                        final_answer = final_answer.strip()
                        
                        if final_answer and len(final_answer) > 10:  # Keep only if meaningful
                            assistant_content = final_answer
                            logger.info(f"🔍 [HISTORY] ✅ Final answer extracted: {final_answer[:150]}...")
                        else:
                            logger.info(f"🔍 [HISTORY] ❌ Final answer too short after cleanup: {len(final_answer)} chars")
                    else:
                        logger.info(f"🔍 [HISTORY] ❌ No final answer extracted from assistant message")
                
                j += 1
            
            # Add assistant response if found
            if assistant_content:
                logger.info(f"🔍 [HISTORY] ✅ Adding assistant response to history: {assistant_content[:100]}...")
                history.append({
                    "role": "assistant",
                    "content": assistant_content
                })
            else:
                logger.info(f"🔍 [HISTORY] ⚠️  No assistant response found for user message at index {i}")
            
            # Move to next message after processed block
            # j already points to next unprocessed message (user or end)
            logger.info(f"🔍 [HISTORY] Moving to next turn, new i={j}")
            i = j
        else:
            # Skip non-user messages at start
            logger.info(f"🔍 [HISTORY] [{i}] Skipping non-user message at start: role={msg.role}")
            i += 1
    
    logger.info(f"🔍 [HISTORY] ✅ Extraction complete: {len(history)} messages in history")
    return history

