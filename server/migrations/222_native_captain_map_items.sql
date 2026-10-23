-- Explicit Wakemu supported inference: sixteen native captain maps yield one26729.
-- Native criterion and callback meaning are exact; no captured server reward edge exists.
CREATE TABLE native_captain_map_item_actions (
 item_ref integer PRIMARY KEY CHECK(item_ref BETWEEN 15368 AND 15383),
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 policy text NOT NULL CHECK(policy='supported_inference_wakemu_one_encyclopedia_per_set'),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$')
);
INSERT INTO native_captain_map_item_actions VALUES
(15368,3090,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15369,3091,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15370,3092,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15371,3093,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15372,3094,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15373,3095,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15374,3096,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15375,3097,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15376,3098,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15377,3099,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15378,3100,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15379,3101,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15380,3102,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15381,3103,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15382,3104,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18'),
(15383,3105,'supported_inference_wakemu_one_encyclopedia_per_set','6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18');
