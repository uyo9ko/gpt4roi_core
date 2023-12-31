
import copy
import torch
from PIL import Image
from functools import partial
from transformers import AutoTokenizer, StoppingCriteria
from gpt4roi.models.spi_llava import SPILlavaMPTForCausalLM
from gpt4roi.train.train import preprocess


class KeywordsStoppingCriteria(StoppingCriteria):
    """Custom stopping criteria for the model's generation process."""
    def __init__(self, keywords, tokenizer, input_ids):
        self.keywords = keywords
        self.keyword_ids = [tokenizer.encode(keyword) for keyword in keywords]
        self.tokenizer = tokenizer
        self.start_len = None
        self.input_ids = input_ids

    def __call__(self, output_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        if self.start_len is None:
            self.start_len = self.input_ids.shape[1]
        else:
            outputs = self.tokenizer.batch_decode(output_ids[:, self.start_len:], skip_special_tokens=True)[0]
            for keyword in self.keywords:
                if keyword in outputs:
                    return True
        return False


def get_init_inputs(img_path, bbox, processor, tokenizer, text):
    """Prepare initial inputs for the model."""
    image = Image.open(img_path).convert('RGB')
    image = processor.preprocess(image, do_center_crop=False, return_tensors='pt')['pixel_values'][0]
    image = torch.nn.functional.interpolate(image.unsqueeze(0), size=(224, 224), mode='bilinear', align_corners=False).squeeze(0)

    pred_bboxes = torch.Tensor(bbox)
    sources = [[{'from': 'human', 'value': text}]]
    data_dict = preprocess(sources, tokenizer)

    return dict(input_ids=data_dict['input_ids'][0],
                labels=data_dict['labels'][0],
                sources=copy.deepcopy(sources),
                init_question=text,
                image=image,
                bboxes=pred_bboxes,
                img_metas=dict(filename=img_path))


def eval_model(model, tokenizer, image_processor, img_path, bbox, text):
    """Evaluate the model with given inputs.
    
    Args:
        model: The model to evaluate.
        tokenizer: The tokenizer to use for text processing.
        image_processor: The image processor to use for image preprocessing.
        img_path: The path to the image to process.
        bbox: The bounding box coordinates as [x1, y1, x2, y2], where:
            (x1, y1) is the top-left corner,
            (x2, y2) is the bottom-right corner,
            w = x2 - x1 is the width of the bounding box, and
            h = y2 - y1 is the height of the bounding box.
        text: The text to process.

    Returns:
        The output IDs generated by the model.
    """
    init_inputs = get_init_inputs(img_path, bbox, image_processor, tokenizer, text)
    model = model.cuda()
    bboxes = init_inputs['bboxes'].cuda()
    image = init_inputs['image']
    input_ids = init_inputs['input_ids'].cuda()[None]

    keywords = ['###']
    stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

    with torch.no_grad():
        model.orig_forward = model.forward
        model.forward = partial(model.orig_forward, img_metas=[None], images=image.unsqueeze(0).half().cuda(), bboxes=[bboxes.half()])
        output_ids = model.generate(input_ids, do_sample=True, temperature=0.2, max_new_tokens=1024, stopping_criteria=[stopping_criteria])

    return output_ids


def eval_model_embeding(model,tokenizer,image_processor, img_path, bbox, input_ids):
    """Evaluate the model with given inputs.
    
    Args:
        model: The model to evaluate.
        tokenizer: The tokenizer to use for text processing.
        image_processor: The image processor to use for image preprocessing.
        img_path: The path to the image to process.
        bbox: The bounding box coordinates as [x1, y1, x2, y2], where:
            (x1, y1) is the top-left corner,
            (x2, y2) is the bottom-right corner,
            w = x2 - x1 is the width of the bounding box, and
            h = y2 - y1 is the height of the bounding box.
        input_ids: The pre-tokenized input IDs.

    Returns:
        The output IDs generated by the model.
    """
    model = model.cuda()
    image = Image.open(img_path).convert('RGB')
    image = image_processor.preprocess(image, do_center_crop=False, return_tensors='pt')['pixel_values'][0]
    image = torch.nn.functional.interpolate(image.unsqueeze(0), size=(224, 224), mode='bilinear', align_corners=False).squeeze(0)

    bboxes = torch.Tensor(bbox).cuda()
    input_ids = input_ids.cuda()

    keywords = ['###']
    stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

    with torch.no_grad():
        model.orig_forward = model.forward
        model.forward = partial(model.orig_forward, img_metas=[None], images=image.unsqueeze(0).half().cuda(), bboxes=[bboxes.half()])
        output_ids = model.generate(input_ids, do_sample=True, temperature=0.2, max_new_tokens=1024, stopping_criteria=[stopping_criteria])

    return output_ids


if __name__ == "__main__":
    # Define the main function here

    # image_processor = CLIPImageProcessor.from_pretrained(
    #     '/data/shenzh_work/shenzh_personal/LLM/clip-vit-large-patch14', torch_dtype=torch.float16)
    # model_name = './checkpoint-1000000'
    # model = SPILlavaMPTForCausalLM.from_pretrained(model_name).cuda()
    # tokenizer = AutoTokenizer.from_pretrained(model_name)
    pass
    
